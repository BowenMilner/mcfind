#include "finders.h"
#include "generator.h"
#include "biomenoise.h"

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>


enum
{
    MCFIND_STRONGHOLD = -1,
};


typedef struct
{
    int x;
    int z;
    int valid;
    int exact;
} mcfind_result_t;


static long long now_ms(void)
{
    struct timespec ts;
    timespec_get(&ts, TIME_UTC);
    return ((long long) ts.tv_sec * 1000LL) + (ts.tv_nsec / 1000000LL);
}


static int floor_div(int value, int divisor)
{
    int quotient = value / divisor;
    int remainder = value % divisor;
    if (remainder != 0 && ((remainder < 0) != (divisor < 0)))
        quotient -= 1;
    return quotient;
}


static double block_distance(int from_x, int from_z, int x, int z)
{
    double dx = (double) x - (double) from_x;
    double dz = (double) z - (double) from_z;
    return sqrt(dx*dx + dz*dz);
}


static void set_error(char *error, int error_len, const char *message)
{
    if (!error || error_len <= 0)
        return;
    snprintf(error, (size_t) error_len, "%s", message);
}


static void insert_result(
    mcfind_result_t *results,
    int *count,
    int capacity,
    int from_x,
    int from_z,
    int x,
    int z,
    int exact
)
{
    double distance = block_distance(from_x, from_z, x, z);
    int position = *count;
    int current;

    if (*count < capacity)
    {
        (*count)++;
    }
    else
    {
        double farthest = block_distance(from_x, from_z, results[capacity - 1].x, results[capacity - 1].z);
        if (distance >= farthest)
            return;
        position = capacity - 1;
    }

    while (position > 0)
    {
        current = position - 1;
        if (!results[current].valid)
            break;
        if (block_distance(from_x, from_z, results[current].x, results[current].z) <= distance)
            break;
        results[position] = results[current];
        position--;
    }

    results[position].x = x;
    results[position].z = z;
    results[position].valid = 1;
    results[position].exact = exact;
}


static int is_structure_valid(
    int structure_type,
    int mc,
    long long seed,
    int x,
    int z,
    Generator *g
)
{
    if (!isViableStructurePos(structure_type, g, x, z, 0))
        return 0;
    if (structure_type == End_City)
    {
        SurfaceNoise sn;
        initSurfaceNoise(&sn, DIM_END, (uint64_t) seed);
        return isViableEndCityTerrain(g, &sn, x, z);
    }
    if (mc >= MC_1_18)
        return isViableStructureTerrain(structure_type, g, x, z);
    return 1;
}


static int scan_region_ring(
    int structure_type,
    int mc,
    long long seed,
    int from_x,
    int from_z,
    int center_rx,
    int center_rz,
    int ring,
    int radius_blocks,
    Generator *g,
    const StructureConfig *config,
    mcfind_result_t *results,
    int *count,
    int capacity,
    long long deadline
)
{
    int rx, rz;
    for (rz = center_rz - ring; rz <= center_rz + ring; rz++)
    {
        for (rx = center_rx - ring; rx <= center_rx + ring; rx++)
        {
            Pos pos;
            double distance;
            if (deadline > 0 && now_ms() > deadline)
                return 2;
            if (ring > 0 &&
                rx != center_rx - ring &&
                rx != center_rx + ring &&
                rz != center_rz - ring &&
                rz != center_rz + ring)
            {
                continue;
            }
            if (!getStructurePos(structure_type, mc, (uint64_t) seed, rx, rz, &pos))
                continue;
            distance = block_distance(from_x, from_z, pos.x, pos.z);
            if (radius_blocks > 0 && distance > (double) radius_blocks)
                continue;
            if (!is_structure_valid(structure_type, mc, seed, pos.x, pos.z, g))
                continue;
            insert_result(results, count, capacity, from_x, from_z, pos.x, pos.z, 1);
        }
    }
    return 1;
}


static int query_regular_structure(
    int structure_type,
    int mc,
    long long seed,
    int from_x,
    int from_z,
    int radius_blocks,
    int limit,
    int timeout_ms,
    mcfind_result_t *results,
    int *count,
    char *error,
    int error_len
)
{
    StructureConfig config;
    Generator g;
    long long deadline = timeout_ms > 0 ? now_ms() + timeout_ms : 0;
    int region_blocks;
    int center_rx;
    int center_rz;
    int ring;
    int max_ring = 0;

    if (!getStructureConfig(structure_type, mc, &config))
    {
        set_error(error, error_len, "Unsupported structure/version combination in cubiomes.");
        return 0;
    }

    setupGenerator(&g, mc, 0);
    applySeed(&g, config.dim, (uint64_t) seed);
    region_blocks = config.regionSize * 16;
    center_rx = floor_div(from_x, region_blocks);
    center_rz = floor_div(from_z, region_blocks);

    if (radius_blocks > 0)
    {
        max_ring = (radius_blocks / region_blocks) + 3;
    }
    else
    {
        max_ring = 512;
    }

    for (ring = 0; ring <= max_ring; ring++)
    {
        int status = scan_region_ring(
            structure_type,
            mc,
            seed,
            from_x,
            from_z,
            center_rx,
            center_rz,
            ring,
            radius_blocks,
            &g,
            &config,
            results,
            count,
            limit,
            deadline
        );
        if (status == 2)
        {
            set_error(error, error_len, "Timed out while scanning cubiomes regions.");
            return 0;
        }
        if (radius_blocks <= 0 && *count >= limit)
        {
            double farthest = block_distance(from_x, from_z, results[*count - 1].x, results[*count - 1].z);
            double conservative_bound = (double) ring * (double) region_blocks;
            if (conservative_bound > farthest + (region_blocks * 2))
                break;
        }
    }
    return 1;
}


static int query_strongholds(
    int mc,
    long long seed,
    int from_x,
    int from_z,
    int radius_blocks,
    int limit,
    int timeout_ms,
    mcfind_result_t *results,
    int *count,
    char *error,
    int error_len
)
{
    StrongholdIter sh;
    Generator g;
    long long deadline = timeout_ms > 0 ? now_ms() + timeout_ms : 0;
    int remaining;
    int origin_distance;

    setupGenerator(&g, mc, 0);
    applySeed(&g, DIM_OVERWORLD, (uint64_t) seed);
    initFirstStronghold(&sh, mc, (uint64_t) seed);
    origin_distance = (int) sqrt((double) from_x * (double) from_x + (double) from_z * (double) from_z);

    while ((remaining = nextStronghold(&sh, &g)) > 0)
    {
        double distance;
        double lower_bound_future;
        if (deadline > 0 && now_ms() > deadline)
        {
            set_error(error, error_len, "Timed out while locating strongholds.");
            return 0;
        }
        distance = block_distance(from_x, from_z, sh.pos.x, sh.pos.z);
        if (radius_blocks <= 0 || distance <= (double) radius_blocks)
            insert_result(results, count, limit, from_x, from_z, sh.pos.x, sh.pos.z, 1);
        if (*count >= limit)
        {
            lower_bound_future = sqrt(
                (double) sh.nextapprox.x * (double) sh.nextapprox.x +
                (double) sh.nextapprox.z * (double) sh.nextapprox.z
            ) - origin_distance - 128.0;
            if (lower_bound_future > block_distance(from_x, from_z, results[*count - 1].x, results[*count - 1].z))
                break;
        }
    }
    return 1;
}


int mcfind_query_structure(
    int structure_type,
    int mc,
    long long seed,
    int from_x,
    int from_z,
    int radius_blocks,
    int limit,
    int timeout_ms,
    mcfind_result_t *results,
    int *count,
    char *error,
    int error_len
)
{
    int i;
    if (!results || !count || limit <= 0)
    {
        set_error(error, error_len, "Invalid result buffer.");
        return 0;
    }
    *count = 0;
    for (i = 0; i < limit; i++)
    {
        results[i].x = 0;
        results[i].z = 0;
        results[i].valid = 0;
        results[i].exact = 0;
    }
    if (structure_type == MCFIND_STRONGHOLD)
        return query_strongholds(mc, seed, from_x, from_z, radius_blocks, limit, timeout_ms, results, count, error, error_len);
    return query_regular_structure(structure_type, mc, seed, from_x, from_z, radius_blocks, limit, timeout_ms, results, count, error, error_len);
}
