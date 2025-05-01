// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import fs from 'fs';
import { mkdir } from 'fs/promises';
import path from 'path';
import { Readable } from 'stream';
import * as stream from 'stream';
import { finished } from 'stream/promises';
import { promisify } from 'util';

import AdmZip from 'adm-zip';
import { isAxiosError } from 'axios';
import dotenv from 'dotenv';
import { groupBy } from 'lodash';

import { createApiModelsService } from '../../../../src/core/models/services/api-models-service';
import { ProjectIdentifier } from '../../../../src/core/projects/core.interface';
import { ProjectProps } from '../../../../src/core/projects/project.interface';
import { createApiProjectService } from '../../../../src/core/projects/services/api-project-service';
import { ProjectSortingOptions } from '../../../../src/core/projects/services/project-service.interface';
import { createApiSupportedAlgorithmsService } from '../../../../src/core/supported-algorithms/services/api-supported-algorithms-service';
import { JobInfoStatus } from '../../../../src/core/tests/dtos/tests.interface';
import { createApiTestsService } from '../../../../src/core/tests/services/api-tests-service';
import { Test } from '../../../../src/core/tests/tests.interface';
import { createApiWorkspacesService } from '../../../../src/core/workspaces/services/api-workspaces-service';
import { WorkspaceIdentifier } from '../../../../src/core/workspaces/services/workspaces.interface';
import { ServiceConfiguration } from '../../api-fixtures';
import { test } from '../../fixtures';
import { TestProject } from '../test-project';

dotenv.config({ path: path.resolve(__dirname, '.env') });

test.setTimeout(1000 * 60 * 60 * 24);

test.describe('Api testing', async () => {
    test.skip('Running tests for each model version', async ({ apiServiceConfiguration, baseURL }) => {
        const workspaceService = createApiWorkspacesService(apiServiceConfiguration);
        const projectService = createApiProjectService(apiServiceConfiguration);
        const testsService = createApiTestsService(apiServiceConfiguration);
        const modelsService = createApiModelsService(apiServiceConfiguration);
        const supportedAlgorithmsService = createApiSupportedAlgorithmsService(apiServiceConfiguration);

        const organization = await apiServiceConfiguration.instance.get<{ organizationId: string }>(
            `${baseURL}/api/v1/personal_access_tokens/organization`
        );

        const organizationId = organization.data.organizationId;
        const workspaces = await workspaceService.getWorkspaces(organizationId);
        const workspaceId = workspaces.at(0)?.id ?? '3a06d5bf-29d2-4ea1-a30f-70e3b0d7f953';

        const workspaceIdentifier = { organizationId, workspaceId };

        const projects = await projectService.getProjects(workspaceIdentifier, {
            sortBy: ProjectSortingOptions.creationDate,
            sortDir: 'asc',
        });

        for (const p of projects.projects) {
            console.log(`[${p.id}]: ${p.name}`);
            const projectIdentifier = { ...workspaceIdentifier, projectId: p.id };
            const project = await projectService.getProject(projectIdentifier);
            const dataset = project.datasets.at(0)!;

            // Required to be able to load models, I feel like we should refactor this
            const supportedAlgorithms =
                await supportedAlgorithmsService.getProjectSupportedAlgorithms(projectIdentifier);

            const tasksWithSupportedAlgorithms = project.tasks.reduce((prev, curr) => {
                return {
                    [curr.id]: supportedAlgorithms.filter(({ domain }) => domain === curr.domain),
                    ...prev,
                };
            }, {});

            // Get all the trained model groups (architectures)
            const modelGroups = await modelsService.getModels(projectIdentifier, tasksWithSupportedAlgorithms);

            for (const modelGroup of modelGroups) {
                console.log('Template: ', modelGroup.modelTemplateName, 'Group: ', modelGroup.groupName);

                for (const version of modelGroup.modelVersions) {
                    console.log(version.groupName, version.version);
                    const modelIdentifier = { ...projectIdentifier, groupId: modelGroup.groupId, modelId: version.id };

                    // Optimize incremental models
                    if (!modelGroup.groupName.includes('SAM')) {
                        try {
                            await modelsService.optimizeModel(modelIdentifier);
                        } catch (e) {
                            if (isAxiosError(e)) {
                                console.log(
                                    `Error optimizing model [${project.name}: ${version.groupName} (${version.version})]:
${e.message}`,
                                    e.response?.data
                                );
                            }
                        }
                    }

                    // Run tests on all optimized models
                    // TODO: this should wait for the optimization to have finished or
                    // this should be a separate script / test
                    const model = await modelsService.getModel(modelIdentifier);

                    for (const optimizedModel of model.optimizedModels) {
                        // ONNX is not supported for inferencing on the server
                        if (optimizedModel.optimizationType === 'ONNX') {
                            continue;
                        }

                        console.log({
                            datasetIds: [dataset.id],
                            modelGroupId: modelGroup.groupId,
                            modelId: optimizedModel.id,
                            name: `Test ${optimizedModel.modelName} - ${dataset.name}`,
                        });

                        try {
                            await testsService.runTest(projectIdentifier, {
                                datasetIds: [dataset.id],
                                modelGroupId: modelGroup.groupId,
                                modelId: optimizedModel.id,
                                name: `Test ${optimizedModel.modelName} - ${dataset.name}`,
                            });
                        } catch (e) {
                            if (isAxiosError(e)) {
                                console.log(
                                    `Error running test model [${project.name}: ${version.groupName} (${version.version}) - ${optimizedModel.modelName}]:
${e.message}`,
                                    e.response?.data
                                );
                            }
                        }
                    }
                }
            }
        }
    });

    async function getAllProjects(
        serviceConfiguration: ServiceConfiguration,
        workspaceIdentifier: WorkspaceIdentifier
    ) {
        const projectService = createApiProjectService(serviceConfiguration);

        let nextPageUrl: string | null | undefined = '';
        const allProjects = [];

        while (nextPageUrl !== undefined && nextPageUrl !== null) {
            const { projects, nextPage } = await projectService.getProjects(
                workspaceIdentifier,
                {
                    sortBy: ProjectSortingOptions.creationDate,
                    sortDir: 'dsc',
                },
                nextPageUrl === '' ? undefined : nextPageUrl
            );

            nextPageUrl = nextPage ? serviceConfiguration.router.PREFIX(nextPage) : undefined;
            allProjects.push(...projects);
        }

        return allProjects;
    }

    test.skip('Shows a test report of all projects', async ({
        apiServiceConfiguration: serviceConfiguration,
        baseURL,
    }) => {
        const workspaceService = createApiWorkspacesService(serviceConfiguration);
        const testsService = createApiTestsService(serviceConfiguration);
        const modelsService = createApiModelsService(serviceConfiguration);
        const supportedAlgorithmsService = createApiSupportedAlgorithmsService(serviceConfiguration);
        const org = await serviceConfiguration.instance.get<{ organizationId: string }>(
            `${baseURL}/api/v1/personal_access_tokens/organization`
        );

        const organizationId = org.data.organizationId;
        const workspaces = await workspaceService.getWorkspaces(organizationId);
        const workspaceId = workspaces.at(0)?.id ?? '3a06d5bf-29d2-4ea1-a30f-70e3b0d7f953';
        const workspaceIdentifier = { organizationId, workspaceId };

        const projects = await getAllProjects(serviceConfiguration, workspaceIdentifier);

        console.log(projects.length);

        const allTests: Array<{ test: Test; project: ProjectProps }> = [];
        for (const project of projects) {
            console.log(`Getting tests for ${project.name}`);
            const projectIdentifier = { ...workspaceIdentifier, projectId: project.id };

            const supportedAlgorithms =
                await supportedAlgorithmsService.getProjectSupportedAlgorithms(projectIdentifier);
            const tasksWithSupportedAlgorithms = project.tasks.reduce((prev, curr) => {
                return {
                    [curr.id]: supportedAlgorithms.filter(({ domain }) => domain === curr.domain),
                    ...prev,
                };
            }, {});

            // Get all the trained model groups (architectures)
            const modelGroups = await modelsService.getModels(projectIdentifier, tasksWithSupportedAlgorithms);

            const tests = await testsService.getTests(projectIdentifier, modelGroups);

            console.log(tests.length);
            tests.forEach((test) => {
                allTests.push({ test, project });
            });
        }

        console.log(allTests.length);
        const testsThatWeAreInterestedIn = allTests.filter(({ test }) => test.jobInfo.status === JobInfoStatus.DONE);

        console.table(
            testsThatWeAreInterestedIn.map(({ test, project }) => {
                return {
                    project: project.name,
                    //name: test.testName,
                    groupName: test.modelInfo.groupName,
                    precision: test.modelInfo.precision,
                    optimization: test.modelInfo.optimizationType,
                    score:
                        test.scores.find((score) => score.labelId === null)?.value ?? `Meh: ${test.scores[0]?.value}`,
                    //modelTemplateId: test.modelInfo.modelTemplateId,
                    status: test.jobInfo.status,

                    projectId: project.id,
                    modelGroupId: test.modelInfo.groupId,
                    modelId: test.modelInfo.id,
                    // Category - should be ignored
                    //modelTemplateName: test.modelInfo.modelTemplateName,
                };
            })
        );

        const grouped = groupBy(testsThatWeAreInterestedIn, ({ test }) => test.modelInfo.groupId);
        console.table(
            Object.keys(grouped).map((modelGroupId) => {
                const testsForModelGroup = grouped[modelGroupId];
                const fp16 = testsForModelGroup.find(({ test }) => test.modelInfo.precision === 'FP16')!;
                const fp32 = testsForModelGroup.find(({ test }) => test.modelInfo.precision === 'FP32')!;
                const int8 = testsForModelGroup.find(({ test }) => test.modelInfo.precision === 'INT8');
                const { project, test } = fp32;

                if (fp16 === undefined) {
                    return {
                        project: project.name,
                        groupName: test.modelInfo.groupName,
                        fp16: undefined,
                        fp32: undefined,
                        diff: undefined,
                        int8: undefined,
                    };
                }

                const fp16Score = fp16.test.scores.find((score) => score.labelId === null)?.value!;
                const fp32Score = fp32.test.scores.find((score) => score.labelId === null)?.value!;
                const int8Score = int8?.test.scores.find((score) => score.labelId === null)?.value;

                return {
                    project: project.name,
                    groupName: test.modelInfo.groupName,
                    fp16: fp16Score,
                    fp32: fp32Score,
                    int8: int8Score,
                    diff: fp32Score - fp16Score,
                    diffInt8: int8Score === undefined ? undefined : fp32Score - int8Score,
                };
            })
        );
    });

    // TODO: need better project pagination?
    test.only('Downloading deployment package', async ({ apiServiceConfiguration, applicationServices }) => {
        const testProject = new TestProject(apiServiceConfiguration);

        await test.step('Fetch workspace details', async () => {
            await testProject.getWorkspace();
        });

        const projectService = createApiProjectService(apiServiceConfiguration);
        const modelsService = createApiModelsService(apiServiceConfiguration);
        const supportedAlgorithmsService = createApiSupportedAlgorithmsService(apiServiceConfiguration);

        const workspaceIdentifier = testProject.workspaceIdentifier();

        const projects = await projectService.getProjects(workspaceIdentifier, {
            sortBy: ProjectSortingOptions.creationDate,
            sortDir: 'asc',
        });

        for (const p of projects.projects) {
            //console.log(`[${p.name}] Start exporting - ${p.id}`);
            const projectIdentifier = { ...workspaceIdentifier, projectId: p.id };
            const project = await projectService.getProject(projectIdentifier);

            const supportedAlgorithms =
                await supportedAlgorithmsService.getProjectSupportedAlgorithms(projectIdentifier);
            const tasksWithSupportedAlgorithms = project.tasks.reduce((prev, curr) => {
                return {
                    [curr.id]: supportedAlgorithms.filter(({ domain }) => domain === curr.domain),
                    ...prev,
                };
            }, {});

            // Get all the trained model groups (architectures)
            const modelGroups = await modelsService.getModels(projectIdentifier, tasksWithSupportedAlgorithms);
            for (const modelGroup of modelGroups) {
                for (const version of modelGroup.modelVersions) {
                    const modelIdentifier = { ...projectIdentifier, groupId: modelGroup.groupId, modelId: version.id };
                    const model = await modelsService.getModel(modelIdentifier);

                    for (const optimizedModel of model.optimizedModels) {
                        // ONNX deployment is not supported
                        if (optimizedModel.optimizationType === 'ONNX') {
                            continue;
                        }

                        const optimizedModelIdentifier = {
                            ...projectIdentifier,
                            modelGroupId: modelGroup.groupId,
                            optimizedModelId: optimizedModel.id,
                        };

                        const ovmsPayload = {
                            package_type: 'ovms',
                            models: [
                                {
                                    model_group_id: optimizedModelIdentifier.modelGroupId,
                                    model_id: optimizedModelIdentifier.optimizedModelId,
                                },
                            ],
                        };

                        const destinationPath = [
                            slugify(project.name),
                            //slugify(modelGroup.groupName),
                            slugify(optimizedModel.modelName),
                            `version-${version.version}`,
                        ];

                        console.log(optimizedModel.modelName);
                        if (slugify(optimizedModel.modelName).includes('segnext')) {
                            if (optimizedModel.modelName.toLocaleLowerCase().includes('fp16')) {
                                console.log('ignoring', destinationPath.join('-'));
                                continue;
                            }
                        }

                        if (!optimizedModel.modelName.includes('FP32')) {
                            continue;
                        }
                        if (optimizedModel.modelName.includes('with XAI')) {
                            continue;
                        }
                        //console.log(destinationPath.join('-'));

                        // if (slugify(optimizedModel.modelName).includes('segnext')) {
                        //     await new Promise((resolve) => setTimeout(resolve, 30_000));

                        //     if (optimizedModel.modelName.toLocaleLowerCase().includes('fp16')) {
                        //         console.log('ignoring', destinationPath.join('-'));
                        //         continue;
                        //     }
                        // }

                        await extractTheStuff(destinationPath, apiServiceConfiguration, projectIdentifier, ovmsPayload);
                        // await extractTheStuff(destinationPath, apiServiceConfiguration, projectIdentifier, {
                        //     ...ovmsPayload,
                        //     package_type: 'geti_sdk',
                        // });
                    }
                }
            }
            //console.log(`[${project.name}] Done exporting`);
        }
    });
});

const pipeline = promisify(stream.pipeline);

async function extractTheStuff(
    dp: string[],
    serviceConfiguration: ServiceConfiguration,
    projectIdentifier: ProjectIdentifier,
    ovmsPayload: {
        package_type: string;
        models: Array<{ model_group_id: string; model_id: string }>;
    }
) {
    const resultPath = path.resolve('./tests/results/geti-2');
    if (!fs.existsSync(resultPath)) {
        await mkdir(resultPath, { recursive: true });
    }

    const destinationFilePath = path.resolve(resultPath, `${dp.join('-')}-${ovmsPayload.package_type}.zip`);
    if (fs.existsSync(destinationFilePath)) {
        //console.log(`Ignoring because the file already exists`);
        return;
    }

    try {
        console.log(`Starting download ${ovmsPayload.package_type}`);
        const response = await serviceConfiguration.instance.post(
            serviceConfiguration.router.DEPLOYMENT_PACKAGE_DOWNLOAD(projectIdentifier),
            ovmsPayload,
            { responseType: 'stream' }
        );

        await pipeline(response.data, fs.createWriteStream(destinationFilePath));
        console.log(`[${ovmsPayload.package_type}] Finished downloading ${destinationFilePath}`);
    } catch (e) {
        console.error('OH NO', e);
        if (isAxiosError(e)) {
            console.log(`[${ovmsPayload.package_type}] Error downloading ${destinationFilePath}: ${e.message}`);
            await new Promise((resolve) => setTimeout(resolve, 5000));
            // console.log('DATA:', e.response?.data);
            return;
        }
    }

    if (!fs.existsSync(destinationFilePath)) {
        console.error('File does not exist', destinationFilePath);
        return;
    }

    const destinationPath = path.resolve(resultPath, ...dp);
    if (!fs.existsSync(destinationPath)) {
        await mkdir(destinationPath, { recursive: true });
    }

    try {
        const zip = new AdmZip(destinationFilePath);
        const extractedPath = path.resolve(destinationPath, ovmsPayload.package_type);
        zip.extractAllTo(extractedPath);
    } catch (error) {
        console.error('Unable to unzip file', destinationFilePath, error);
    }
}

function slugify(str: string) {
    str = str.replace(/^\s+|\s+$/g, ''); // trim leading/trailing white space
    str = str.toLowerCase(); // convert string to lowercase
    str = str
        .replace(/[^a-z0-9 -]/g, '') // remove any non-alphanumeric characters
        .replace(/\s+/g, '-') // replace spaces with hyphens
        .replace(/-+/g, '-'); // remove consecutive hyphens
    return str;
}
