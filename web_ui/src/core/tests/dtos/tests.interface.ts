// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import { OptimizationTypesDTO } from '../../models/dtos/model-details.interface';
import { TASK_TYPE } from '../../projects/dtos/task.interface';

export enum JobInfoStatus {
    PENDING = 'PENDING',
    INFERRING = 'INFERRING',
    EVALUATING = 'EVALUATING',
    DONE = 'DONE',
    CREATING_DATASET = 'CREATING_DATASET',
    FAILED = 'FAILED',
    ERROR = 'ERROR',
}

export enum ScoreMetricDTO {
    GLOBAL = 'global',
    LOCAL = 'local',
}

export interface TestScoreDTO {
    label_id: string | null;
    name: string;
    value: number;
}

export interface RunTestBodyDTO {
    name: string;
    model_group_id: string;
    model_id: string;
    dataset_ids: string[];
    metric?: ScoreMetricDTO;
}

export interface TestDTO {
    id: string;
    name: string;
    creation_time: string;
    job_info?: {
        id: string;
        status: JobInfoStatus;
    };
    model_info: {
        id: string;
        group_id: string;
        template_id: string;
        task_type: TASK_TYPE;
        n_labels: number;
        version: number;
        optimization_type: OptimizationTypesDTO;
        precision: string[];
    };
    datasets_info: {
        id: string;
        name: string;
        is_deleted: boolean;
        n_images: number;
        n_frames: number;
        n_samples: number;
    }[];
    scores: TestScoreDTO[];
}

export interface TestsDTO {
    test_results: TestDTO[];
}
