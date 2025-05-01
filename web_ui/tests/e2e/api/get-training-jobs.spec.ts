// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import fs from 'fs';
import path from 'path';

import _ from 'lodash';

import { JobType } from '../../../src/core/jobs/jobs.const';
import { Job, JobOptimization, JobTask, JobTest } from '../../../src/core/jobs/jobs.interface';
import { isJobOptimization, isJobTest, isJobTrain } from '../../../src/core/jobs/utils';
import { TrainingModelInfoType } from '../../../src/core/statistics/model-statistics.interface';
import { test } from '../fixtures';
import { collect, filter, groupBy, jobsIterator, map, pagesIterator } from './iterators';
import { TestProject } from './test-project';

enum TrainingMetadataKeys {
    TRAINING_DATE = 'training date',
    TRAINING_JOB = 'training job',
    TRAINING_DURATION = 'training duration',
}

const mapToTable = (job: Job) => {
    let extra = {};
    if (isJobTrain(job)) {
        extra = {
            ...extra,
            name: job.metadata.project.name,
            task: job.metadata.task.name,
            model: job.metadata.task.modelArchitecture,
            model_template_id: job.metadata.task.modelTemplateId,
        };
    }
    if (isJobOptimization(job)) {
        extra = {
            ...extra,
            name: job.metadata.project.name,
            model: job.metadata.task.modelArchitecture,
            model_template_id: job.metadata.task.modelTemplateId,
        };
    }
    if (isJobTest(job)) {
        // job.metadata.test.datasets
        //  job.metadata.test.model.id
        //  job.metadata.test.model.modelTemplateId
        //  job.metadata.test.model.architectureName
        //  job.metadata.test.model.optimizationType
        // job.metadata.task.taskId
        // job.metadata.project.id

        extra = {
            ...extra,
            name: job.metadata.project.name,
            model: job.metadata.test.model.architectureName,
            model_template_id: job.metadata.test.model.modelTemplateId,
        };
    }

    return {
        // state: job.state,
        name: job.name,
        type: job.type,
        ...extra,
        // 'creation time': job.creationTime,
        // 'start time': job.startTime,
        'duration (s)': (new Date(job?.endTime ?? '').getTime() - new Date(job?.startTime ?? '').getTime()) / 1000,
        'step 1 (s)': job.steps[0]?.duration,
        'step 2 (s)': job.steps[1]?.duration,
        'step 3 (s)': job.steps[2]?.duration,
        // 'step 1': `${job.steps[0]?.state} - ${job.steps[0]?.message}`,
        // 'step 2': `${job.steps[1]?.state} - ${job.steps[1]?.message}`,
        // 'step 3': `${job.steps[2]?.state} - ${job.steps[2]?.message}`,
    };
};

test('Get training and optimization jobs', async ({ apiServiceConfiguration, applicationServices }) => {
    const cardDetectionProject = new TestProject(apiServiceConfiguration);

    await test.step('Fetch workspace details', async () => {
        await cardDetectionProject.getWorkspace();
    });

    const workspaceIdentifier = cardDetectionProject.workspaceIdentifier();

    console.log({
        workspaceIdentifier,
    });

    const cardDetectionProjectId = '67b88d86c3d4b31dec9ab3bd';
    // const modelGroups = await applicationServices.modelsService.getModels(
    //     {
    //         ...workspaceIdentifier,
    //         projectId: cardDetectionProjectId,
    //     },
    //     []
    // );

    // console.table(modelGroups);

    // const stats = await Promise.all(
    //     modelGroups.map(async (group) => {
    //         const version = group.modelVersions.at(-1);
    //         const modelStatistics = await applicationServices.modelStatisticsService.getModelStatistics({
    //             ...workspaceIdentifier,
    //             projectId: cardDetectionProjectId,
    //             modelId: version?.id,
    //             groupId: group.groupId,
    //         });

    //         console.log(modelStatistics);
    //         const x = getModelStatistics(modelStatistics);

    //         return {
    //             model: version?.groupName,
    //             'Training date': x.trainingMetadata['0'].value,
    //             'Training job duration': x.trainingMetadata['1'].value,
    //             'Training duration': x.trainingMetadata['2'].value,
    //         };
    //         // return modelStatistics;
    //     })
    // );

    // console.table(stats);

    // return;

    const jobsService = applicationServices.jobsService;

    const cardProjects = [
        '67b88889c3d4b31dec9ab03e',
        '67b88923c3d4b31dec9ab1ca',
        '67b88a9ec3d4b31dec9ab271',
        '67b88c37c3d4b31dec9ab317',
        '67b88d86c3d4b31dec9ab3bd',
        '67b88e8fc3d4b31dec9ab463',
    ];
    // const tests = (
    //     await Promise.all(
    //         cardProjects.map((projectId) => {
    //             return applicationServices.testsService.getTests({ ...workspaceIdentifier, projectId }, []);
    //         })
    //     )
    // ).flatMap((x) => x);
    // console.log(tests, tests.length);
    // return;

    const jobs = await collect(
        map(
            filter(
                jobsIterator(workspaceIdentifier, jobsService, undefined, [
                    JobType.TRAIN,
                    JobType.OPTIMIZATION_POT,
                    JobType.TEST,
                ]),
                (job): job is JobTask | JobOptimization | JobTest => {
                    if (isJobTest(job)) {
                        return (
                            //cardProjects.includes(job.metadata.project.id) &&
                            job.metadata.test.datasets[0].name === 'Testing set 1'
                        );
                    }

                    if (!isJobTrain(job) && !isJobOptimization(job)) {
                        if (!isJobTest(job)) {
                            return false;
                        }
                        //return false;
                    }
                    return true; //cardProjects.includes(job.metadata.project.id);
                }
            ),
            (job) => {
                //console.log(job);
                //return job;
                // if (!isJobTrain(job) && !isJobOptimization(job) && !isJobTest(job)) {
                //     return {};
                // }
                return job;
            }
        )
    );

    const jobsPath = path.resolve(__dirname, './jobs.json');
    console.table(jobs.map(mapToTable));
    console.log(jobsPath);

    const recommendedModels = [
        'EfficientNet-B0',
        'PADIM',
        'MaskRCNN-EfficientNetB2B',
        'Lite-HRNet-18-mod2',
        'MaskRCNN-EfficientNetB2B',
        'MobileNetV2-ATSS',
    ];
    console.table(
        jobs
            .filter((job) => {
                if (isJobTrain(job) || isJobOptimization(job)) {
                    return recommendedModels.includes(job.metadata.task.modelArchitecture ?? '');
                }
                return false;
            })
            .map(mapToTable)
    );
    console.table(
        jobs
            .filter((job) => {
                if (isJobTrain(job) || isJobOptimization(job)) {
                    return recommendedModels.includes(job.metadata.task.modelArchitecture ?? '');
                }
                return false;
            })
            .map(mapToTable)
    );

    console.table(
        jobs
            .filter((job): job is JobTest => {
                if (isJobTest(job)) {
                    return recommendedModels.includes(job.metadata.test.model.architectureName);
                }
                return false;
            })
            .map((job) => {
                const m = mapToTable(job);
                delete m['step 2 (s)'];
                delete m['step 3 (s)'];
                return {
                    ...m,
                    dataset: job.metadata.test.datasets[0].name,
                    //architectureName: job.metadata.test.model.architectureName,
                    optimization: `${job.metadata.test.model.precision[0]} - ${job.metadata.test.model.optimizationType}${job.metadata.test.model.hasExplainableAI ? ' - XAI' : ''}`,
                    //optimizationType: job.metadata.test.model.optimizationType,
                    //precision: job.metadata.test.model.precision,
                    //xai: job.metadata.test.model.hasExplainableAI,
                };
            })
    );

    // const __filename = fileURLToPath(import.meta.url);
    // const __dirname = path.dirname(__filename);

    //fs.writeFileSync(jobsPath, JSON.stringify(trainedJobs, null, 2));

    const byProject = _.groupBy(jobs, (job) => job.metadata.project.name);
    console.log(
        _.mapValues(byProject, (jobs) => {
            const byJobType = _.groupBy(jobs, (job) => job.type);
            return Object.keys(byJobType).map((type) => {
                return {
                    type,
                    duration: byJobType[type].reduce((total, job) => {
                        const d =
                            (new Date(job?.endTime ?? '').getTime() - new Date(job?.startTime ?? '').getTime()) / 1000;
                        return d / 60 + total;
                    }, 0),
                };
            });

            return {
                jobs: _.groupBy(jobs, (job) => job.type),
                models: _.groupBy(jobs, (job) => job.metadata.task.modelArchitecture),
            };
        })
    );

    console.table(
        jobs
            .filter((job) => {
                return isJobTrain(job); // && job.metadata.project.id === cardDetectionProjectId;
            })
            .map((job) => {
                return { ...mapToTable(job) };
            })
    );

    //console.log(byProject);
});
