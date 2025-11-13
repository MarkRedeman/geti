// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import { buildSegmentAnythingInstance, ExecutionProviders } from '@geti/smart-tools/segment-anything';
import { expose, proxy } from 'comlink';

const WorkerApi = {
    build: async (useWebGPU = false, executionProviders?: ExecutionProviders) => {
        const instance = await buildSegmentAnythingInstance(useWebGPU, executionProviders);

        return proxy(instance);
    },
};

expose(WorkerApi);
