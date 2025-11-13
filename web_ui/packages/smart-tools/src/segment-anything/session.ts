// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import type { InferenceSession } from 'onnxruntime-common';

//import * as ort from 'onnxruntime-web/webgpu';

import { loadSource } from '../utils/tool-utils';
import { SessionParameters, sessionParams } from '../utils/wasm-utils';

type ORT = typeof import('onnxruntime-web');

const loadModel = async (modelPath: string): Promise<ArrayBufferLike | undefined> => {
    return await (await loadSource(modelPath))?.arrayBuffer();
};

const PATHS = {
    wasm: {
        wasm: new URL(
            '../../../../node_modules/onnxruntime-web/dist/ort-wasm-simd-threaded.wasm',
            import.meta.url
        ).toString(),
        mjs: new URL(
            '../../../../node_modules/onnxruntime-web/dist/ort-wasm-simd-threaded.mjs',
            import.meta.url
        ).toString(),
    },
    webgpu: {
        wasm: new URL(
            '../../../../node_modules/onnxruntime-web/dist/ort-wasm-simd-threaded.jsep.wasm',
            import.meta.url
        ).toString(),
        mjs: new URL(
            '../../../../node_modules/onnxruntime-web/dist/ort-wasm-simd-threaded.jsep.mjs',
            import.meta.url
        ).toString(),
    },
};

type ExecutionModel = 'cpu' | 'webgpu' | 'webnn-gpu' | 'webnn-npu' | 'webnn';

console.log(PATHS);

// use a dynamic import to avoid bundling the entire onnxruntime-web package
let ort: ORT | null = null;
export const getOrt = async (useWebGPU: boolean): Promise<ORT> => {
    console.log('load ort', useWebGPU);
    if (ort !== null) {
        return ort;
    }
    if (useWebGPU) {
        ort = (await import('onnxruntime-web/webgpu')).default;
    } else {
        ort = (await import('onnxruntime-web')).default;
    }
    return ort;
};

type SessionOptions = InferenceSession.SessionOptions;
export type ExecutionProviders = SessionOptions['executionProviders'];

export class Session {
    ortSession: InferenceSession | undefined;
    params: SessionParameters;

    constructor(
        private useWebGPU = true,
        private executionProviders?: ExecutionProviders
    ) {
        this.params = sessionParams;

        console.log('session', { useWebGPU, executionProviders });

        this.executionProviders =
            this.executionProviders ??
            (this.useWebGPU === false ? [{ name: 'cpu' }] : [{ name: 'webnn', deviceType: 'cpu' }]);
    }

    public async init(modelPath: string) {
        const ort = await getOrt(this.useWebGPU);
        ort.env.wasm.numThreads = this.params.numThreads;
        ort.env.wasm.wasmPaths = this.params.wasmRoot;
        ort.env.wasm.simd = true;

        ort.env.debug = true;
        ort.env.wasm.proxy = true;
        ort.env.wasm.wasmPaths = {
            mjs: this.useWebGPU ? PATHS.webgpu.mjs : PATHS.wasm.mjs,
            wasm: this.useWebGPU ? PATHS.webgpu.wasm : PATHS.wasm.wasm,
        };

        const modelData = await loadModel(modelPath);

        if (!modelData) {
            throw new Error(`Unable to load model from "${modelPath}"`);
        }

        console.log('create session', this.executionProviders);
        const session = await ort.InferenceSession.create(modelData, {
            executionProviders: this.executionProviders,
            graphOptimizationLevel: 'all',
            executionMode: 'parallel',
        });

        this.ortSession = session;
    }

    public async run(input: InferenceSession.OnnxValueMapType): Promise<InferenceSession.OnnxValueMapType> {
        if (!this.ortSession) {
            throw Error('the session is not initialized. Call `init()` method first.');
        }
        return await this.ortSession.run(input);
    }

    public inputNames(): readonly string[] {
        if (!this.ortSession) {
            throw Error('the session is not initialized. Call `init()` method first.');
        }
        return this.ortSession.inputNames;
    }

    public outputNames(): readonly string[] {
        if (!this.ortSession) {
            throw Error('the session is not initialized. Call `init()` method first.');
        }
        return this.ortSession.outputNames;
    }
}
