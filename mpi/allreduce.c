#include <mpi.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    int rank, size;
    MPI_Init(&argc, &argv);
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);

    // 默认 50 MB
    long nbytes = 50 * 1024 * 1024;
    if (argc > 1) {
        nbytes = atol(argv[1]);
        if (nbytes <= 0) nbytes = 50 * 1024 * 1024;
    }

    // 使用 double 代替 byte，避免 MPI_SUM 出错
    long count = nbytes / sizeof(double);
    double *sendbuf = (double*)malloc(count * sizeof(double));
    double *recvbuf = (double*)malloc(count * sizeof(double));
    if (!sendbuf || !recvbuf) {
        fprintf(stderr, "Memory allocation failed\n");
        MPI_Abort(MPI_COMM_WORLD, 1);
    }

    // 初始化发送缓冲区
    for (long i = 0; i < count; i++) sendbuf[i] = 1.0;

    // 全体同步
    MPI_Barrier(MPI_COMM_WORLD);
    double start = MPI_Wtime();

    // 执行 Allreduce
    MPI_Allreduce(sendbuf, recvbuf, count, MPI_DOUBLE, MPI_SUM, MPI_COMM_WORLD);

    double end = MPI_Wtime();
    double elapsed = end - start;

    // rank 0 打印吞吐量和带宽利用率
    if (rank == 0) {
        double total_bits = count * sizeof(double) * 8.0;
        double throughput_mbps = total_bits / (elapsed * 1e6);
        double bandwidth = 100.0; // Mbit/s，可根据 platform.xml 修改
        double utilization = throughput_mbps * 3 / bandwidth * 100.0;

        printf("AllReduce data size: %.2f MB\n", nbytes / 1024.0 / 1024.0);
        printf("Elapsed time: %.6f s\n", elapsed);
        printf("Throughput: %.3f Mbit/s\n", throughput_mbps);
        printf("Bandwidth utilization: %.2f%%\n", utilization);

        // 简单验证结果
        printf("First element after AllReduce: %f (should be %.0f)\n", 
               recvbuf[0], 1.0 * size);
    }

    free(sendbuf);
    free(recvbuf);
    MPI_Finalize();
    return 0;
}
