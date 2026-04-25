#pragma once

#include <cuda_runtime.h>
#include <c10/cuda/CUDAException.h>

template <typename T, typename U>
__host__ __device__ inline auto THCCeilDiv(T a, U b) -> decltype((a + b - 1) / b) {
  return (a + b - 1) / b;
}

#define THCudaCheck(EXPR) C10_CUDA_CHECK(EXPR)
