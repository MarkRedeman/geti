// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import fs from 'fs';
import { openAsBlob } from 'node:fs';
import path from 'path';

import { isAxiosError } from 'axios';
import dotenv from 'dotenv';
import { partition, sortBy } from 'lodash';
import { v4 as uuidv4 } from 'uuid';

import { Annotation } from '../../../../src/core/annotations/annotation.interface';
import { createApiAnnotationService } from '../../../../src/core/annotations/services/api-annotation-service';
import { ShapeType } from '../../../../src/core/annotations/shapetype.enum';
import { JobState, JobType } from '../../../../src/core/jobs/jobs.const';
import { createApiJobsService } from '../../../../src/core/jobs/services/api-jobs-service';
import { isJobTrain } from '../../../../src/core/jobs/utils';
import { LABEL_BEHAVIOUR, LabelsRelationType } from '../../../../src/core/labels/label.interface';
import { MEDIA_GROUP } from '../../../../src/core/media/base-media.interface';
import { getMediaItemFromDTO } from '../../../../src/core/media/services/utils';
import { createApiModelsService } from '../../../../src/core/models/services/api-models-service';
import { DOMAIN } from '../../../../src/core/projects/core.interface';
import { createApiProjectService } from '../../../../src/core/projects/services/api-project-service';
import { createApiSupportedAlgorithmsService } from '../../../../src/core/supported-algorithms/services/api-supported-algorithms-service';
import { createApiTestsService } from '../../../../src/core/tests/services/api-tests-service';
import { delay } from '../../../../src/shared/utils';
import { getMockedTreeLabel } from '../../../../src/test-utils/mocked-items-factory/mocked-labels';
import { resolveDatasetPath } from '../../../utils/dataset';
import { test } from '../../fixtures';
import { loadCardAnnotations } from '../../utils';
import { TestProject } from './../test-project';

dotenv.config({ path: path.resolve(__dirname, '.env') });

test.setTimeout(1000 * 60 * 60 * 24);

const configuration = {
    projectId: undefined,
    projectName: 'Card detection',

    uploadMedia: [
        resolveDatasetPath(`cards/hearts`),
        resolveDatasetPath(`cards/diamonds`),
        resolveDatasetPath(`cards/spades`),
        resolveDatasetPath(`cards/clubs`),
    ],
    trainAll: true,
    trainModels: [
        { modelTemplateId: 'Object_Detection_ResNeXt101_ATSS', optimize: true },
        { modelTemplateId: 'Custom_Object_Detection_Gen3_ATSS', optimize: true },
        { modelTemplateId: 'Object_Detection_RTDetr_50', optimize: true },
        { modelTemplateId: 'Custom_Object_Detection_Gen3_SSD', optimize: true },
        { modelTemplateId: 'Object_Detection_RTMDet_tiny', optimize: true },
        { modelTemplateId: 'Object_Detection_RTDetr_18', optimize: true },
        { modelTemplateId: 'Object_Detection_YOLOX_S', optimize: true },
        { modelTemplateId: 'Object_Detection_YOLOX_L', optimize: true },
        { modelTemplateId: 'Custom_Object_Detection_YOLOX', optimize: true },
        { modelTemplateId: 'Object_Detection_YOLOX_X', optimize: true },
        { modelTemplateId: 'Object_Detection_RTDetr_101', optimize: true },
    ],
};

const lastSegment = (s: string) => s.substring(s.lastIndexOf('/') + 1);

test('Create a card detection project', async ({ apiServiceConfiguration }) => {
    const cardDetectionProject = new TestProject(apiServiceConfiguration);

    await test.step('Fetch workspace details', async () => {
        await cardDetectionProject.getWorkspace();
    });

    const workspaceIdentifier = cardDetectionProject.workspaceIdentifier();

    await test.step('Create a new project', async () => {
        if (configuration.projectId) {
            cardDetectionProject.projectId = configuration.projectId;
            return;
        }

        const projectService = createApiProjectService(apiServiceConfiguration);
        const project = await projectService.createProject(
            workspaceIdentifier,
            configuration.projectName,
            [DOMAIN.DETECTION],
            [
                {
                    domain: DOMAIN.DETECTION,
                    labels: [
                        getMockedTreeLabel({
                            name: 'Card',
                            group: 'Card',
                            behaviour: LABEL_BEHAVIOUR.LOCAL,
                            color: '#80e9af',
                        }),
                    ],
                    relation: LabelsRelationType.MIXED,
                },
            ]
        );

        cardDetectionProject.projectId = project.id;
    });

    const projectIdentifier = cardDetectionProject.projectIdentifier();
    const projectService = createApiProjectService(apiServiceConfiguration);
    const project = await projectService.getProject(projectIdentifier);
    const datasetIdentifier = {
        ...projectIdentifier,
        datasetId: project.datasets[0].id,
    };

    // Disable auto training

    await test.step('Upload and annotate images', async () => {
        const cardAnnotations = loadCardAnnotations();
        const annotationsService = createApiAnnotationService(apiServiceConfiguration);

        const cardLabel = project.labels[0];

        for (const path of configuration.uploadMedia) {
            const suit = lastSegment(path);

            await test.step(`Uploading cards of suit ${suit}`, async () => {
                const path = resolveDatasetPath(`cards/${suit.toLocaleLowerCase()}`);
                const files = fs.readdirSync(path).map((filename) => ({
                    path: resolveDatasetPath(path, filename),
                    filename,
                }));

                for (const file of files) {
                    await test.step(`Annotate image ${file.filename}`, async () => {
                        const filenameWithoutExtension = file.filename.replace(/\.[^/.]+$/, '');
                        const cardAnnotation = cardAnnotations.find((image) => image.name === filenameWithoutExtension);
                        const formData = new FormData();
                        formData.append('file', await openAsBlob(file.path), file.filename);

                        // Note: atm we can't use the media service due to it
                        // relying on behviour of a brower File
                        const result = await apiServiceConfiguration.instance.post(
                            apiServiceConfiguration.router.MEDIA_UPLOAD(datasetIdentifier, MEDIA_GROUP.IMAGES),
                            formData,
                            { headers: { 'content-type': 'multipart/form-data' } }
                        );

                        const mediaItem = getMediaItemFromDTO(
                            datasetIdentifier,
                            result.data,
                            apiServiceConfiguration.router
                        );

                        const annotations =
                            cardAnnotation?.annotations.map((card, idx): Annotation => {
                                return {
                                    id: uuidv4(),
                                    isHidden: false,
                                    isLocked: false,
                                    isSelected: false,
                                    labels: [{ ...cardLabel, source: { userId: 'api' } }],
                                    shape: { shapeType: ShapeType.Rect, ...card.shape },
                                    zIndex: idx,
                                };
                            }) ?? [];

                        await annotationsService.saveAnnotations(datasetIdentifier, mediaItem, annotations);
                    });
                }
            });
        }
    });

    const supportedAlgorithmsService = createApiSupportedAlgorithmsService(apiServiceConfiguration);
    const supportedAlgorithms = await supportedAlgorithmsService.getProjectSupportedAlgorithms(projectIdentifier);
    const tasksWithSupportedAlgorithms = project.tasks.reduce((prev, curr) => {
        return {
            [curr.id]: supportedAlgorithms.filter(({ domain }) => domain === curr.domain),
            ...prev,
        };
    }, {});

    await test.step('Start training for all model architectures', async () => {
        console.log('Getting jobs');
        const jobsService = createApiJobsService(apiServiceConfiguration);
        const { jobs } = await jobsService.getJobs(
            workspaceIdentifier,
            {
                projectId: projectIdentifier.projectId,
                jobTypes: [JobType.TRAIN],
                limit: 100,
            },
            undefined
        );

        console.log('Getting model groups');
        const modelsService = createApiModelsService(apiServiceConfiguration);
        const modelGroups = await modelsService.getModels(projectIdentifier, tasksWithSupportedAlgorithms);

        for (const task of project.tasks) {
            console.log(`Making sure all models are trained for ${task.title}`);
            const trainingJobs = jobs.filter((job) => {
                return isJobTrain(job) && job.metadata.task.taskId === task.id;
            });

            // Filter
            const modelTemplateIdsToIgnore = new Set([
                ...trainingJobs.map((job) => (isJobTrain(job) ? job.metadata.task.modelTemplateId : '')),
                ...modelGroups.filter((group) => group.taskId === task.id).map((group) => group.modelTemplateId),
            ]);

            console.log(modelTemplateIdsToIgnore);

            const algorithms = supportedAlgorithms.filter(({ domain }) =>
                project.tasks.some((task) => task.domain === domain)
            );
            const [_, algorithmsNotYetTrained] = partition(algorithms, (algorithm) => {
                return modelTemplateIdsToIgnore.has(algorithm.modelTemplateId);
            });

            console.log(
                algorithms.map((a) => a.modelTemplateId),
                _.map((a) => a.modelTemplateId),
                algorithmsNotYetTrained.map((a) => a.modelTemplateId)
            );

            for (const algorithm of algorithmsNotYetTrained) {
                // Only train configured models
                if (
                    configuration.trainAll === false &&
                    !configuration.trainModels.some(
                        ({ modelTemplateId }) => modelTemplateId === algorithm.modelTemplateId
                    )
                ) {
                    continue;
                }

                console.log(`Train model ${task.title} - ${algorithm.name}`);
                await modelsService.trainModel(projectIdentifier, {
                    task_id: task.id,
                    train_from_scratch: false,
                    model_template_id: algorithm.modelTemplateId,
                });
            }
        }
    });

    await test.step('Waiting for training job', async () => {
        const jobsService = createApiJobsService(apiServiceConfiguration);
        console.log('Start fetching jobs');

        let isTraining = true;

        while (isTraining) {
            const { jobs } = await jobsService.getJobs(
                workspaceIdentifier,
                {
                    projectId: projectIdentifier.projectId,
                    jobTypes: [JobType.TRAIN],
                    limit: 100,
                },
                undefined
            );

            const activeJobs = jobs.filter((job) => [JobState.RUNNING, JobState.SCHEDULED].includes(job.state));

            isTraining = activeJobs.length > 0;
            if (isTraining === false) {
                break;
            }

            const now = new Date();
            console.log(`${now.toISOString()} - Training... (${activeJobs.length} / ${jobs.length})`);

            await delay(30_000);
        }

        console.log('All training jobs have finished');
    });

    await test.step('Start model optimization for all models', async () => {
        console.log('Getting model groups');
        const modelsService = createApiModelsService(apiServiceConfiguration);
        const modelGroups = await modelsService.getModels(projectIdentifier, tasksWithSupportedAlgorithms);

        const models = modelGroups.flatMap((group) => group.modelVersions);
        for (const model of models) {
            const modelIdentifier = { ...projectIdentifier, groupId: model.groupId, modelId: model.id };

            if (model.groupName.includes('SAM')) {
                continue;
            }

            // TODO: Skip if model is already optimized

            // Optimize incremental models
            console.log(`Optimizing - ${model.groupName} ${model.version}`);
            await modelsService.optimizeModel(modelIdentifier).catch((e) => {
                if (isAxiosError(e)) {
                    console.log(
                        `Error optimizing model [${project.name}: ${model.groupName} (${model.version})]:
                ${e.message}`,
                        e.response?.data
                    );
                }
            });
        }
    });

    await test.step('Waiting for optimization jobs to finish', async () => {
        const jobsService = createApiJobsService(apiServiceConfiguration);
        console.log('Start fetching jobs');

        let isOptimizing = true;

        while (isOptimizing) {
            const { jobs } = await jobsService.getJobs(
                workspaceIdentifier,
                {
                    projectId: projectIdentifier.projectId,
                    jobTypes: [JobType.OPTIMIZATION_POT],
                    limit: 100,
                },
                undefined
            );

            const activeJobs = jobs.filter((job) => [JobState.RUNNING, JobState.SCHEDULED].includes(job.state));

            isOptimizing = activeJobs.length > 0;
            if (isOptimizing === false) {
                break;
            }

            const now = new Date();
            console.log(`${now.toISOString()} - Optimizing... (${activeJobs.length} / ${jobs.length})`);

            await delay(30_000);
        }

        console.log('All optimization jobs have finished');
    });

    await test.step('Run tests for each model version', async () => {
        console.log('Getting model groups');
        const modelsService = createApiModelsService(apiServiceConfiguration);
        const modelGroups = await modelsService.getModels(projectIdentifier, tasksWithSupportedAlgorithms);

        const models = modelGroups.flatMap((group) => group.modelVersions);
        const testsService = createApiTestsService(apiServiceConfiguration);
        for (const model of models) {
            const modelIdentifier = { ...projectIdentifier, groupId: model.groupId, modelId: model.id };

            if (model.groupName.includes('SAM')) {
                continue;
            }
            const { optimizedModels } = await modelsService.getModel(modelIdentifier);

            for (const optimizedModel of optimizedModels) {
                // ONNX models are not supported by model testing
                if (optimizedModel.optimizationType === 'ONNX') {
                    continue;
                }

                for (const dataset of project.datasets) {
                    // Optimize incremental models
                    console.log(`Testing - ${optimizedModel.modelName} ${model.version}`);
                    await testsService
                        .runTest(projectIdentifier, {
                            datasetIds: [dataset.id],
                            modelGroupId: model.groupId,
                            modelId: optimizedModel.id,
                            name: `${optimizedModel.modelName} - ${dataset.name}`,
                        })
                        .catch((e) => {
                            if (isAxiosError(e)) {
                                console.log(
                                    `Error optimizing model [${project.name}: ${model.groupName} (${model.version})]:
                            ${e.message}`,
                                    e.response?.data
                                );
                            }
                        });
                }
            }
        }
    });
    await test.step('Export models', async () => {
        // TODO
    });

    await test.step('Export deployments', async () => {
        // TODO
    });

    await test.step('Waiting for model testing jobs to finish', async () => {
        const jobsService = createApiJobsService(apiServiceConfiguration);
        console.log('Start fetching jobs');

        let isModelTesting = true;

        while (isModelTesting) {
            const { jobs } = await jobsService.getJobs(
                workspaceIdentifier,
                {
                    projectId: projectIdentifier.projectId,
                    jobTypes: [JobType.TEST],
                    limit: 100,
                },
                undefined
            );

            const activeJobs = jobs.filter((job) => [JobState.RUNNING, JobState.SCHEDULED].includes(job.state));

            isModelTesting = activeJobs.length > 0;
            if (isModelTesting === false) {
                break;
            }

            const now = new Date();
            console.log(`${now.toISOString()} - Testing... (${activeJobs.length} / ${jobs.length})`);

            await delay(30_000);
        }

        console.log('All model testing jobs have finished');
    });
});
