// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import { ExecutionProviders } from '@geti/smart-tools/segment-anything';
import { useQuery } from '@tanstack/react-query';
import { Remote, wrap } from 'comlink';
import { useSearchParams } from 'react-router-dom';

import { AlgorithmType } from './algorithm.interface';
import { MapAlgorithmToInstance, WorkerFactory } from './load-webworker.interface';
import { getWorker } from './utils';

export const useLoadAIWebworker = <T extends AlgorithmType>(algorithmType: T) => {
    const [searchParams] = useSearchParams();

    const { data, isLoading, isSuccess, isError } = useQuery<Remote<MapAlgorithmToInstance[T]>>({
        queryKey: ['workers', algorithmType],
        queryFn: async () => {
            const baseWorker = getWorker(algorithmType);
            const worker = wrap<WorkerFactory<T>>(baseWorker);

            if (searchParams.has('webgpu')) {
                const executionProviders: ExecutionProviders = [{ name: 'webgpu' }];

                console.log('[WEBGPU] build with', executionProviders);

                // @ts-expect-error meh
                return worker.build(true, executionProviders);
            }

            if (searchParams.has('webnn')) {
                const deviceType = searchParams.get('webnn') ?? 'gpu';
                const executionProviders: ExecutionProviders = [{ name: 'webnn', deviceType: deviceType }];

                console.log('[WEBNN] build with', executionProviders);

                // @ts-expect-error meh
                return worker.build(true, executionProviders);
            }

            // TODO: allow passing argumentsto build
            return worker.build();
        },
        staleTime: Infinity,
    });

    return { worker: data, isLoading, isSuccess, isError };
};
