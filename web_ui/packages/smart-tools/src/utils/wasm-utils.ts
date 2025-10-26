// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

export interface SessionParameters {
    numThreads: number;
    executionProviders: string[];
    wasmRoot?: string | Record<string, string>;
}

export const sessionParams: SessionParameters = {
    numThreads: 0,
    executionProviders: ['cpu'],
    //wasmRoot: wasmPaths,
};
