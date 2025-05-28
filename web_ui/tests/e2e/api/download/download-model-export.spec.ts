// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import fs from 'fs';
import { mkdir } from 'fs/promises';
import path from 'path';
import * as stream from 'stream';
import { promisify } from 'util';

import AdmZip from 'adm-zip';
import { isAxiosError } from 'axios';

import { createApiModelsService } from '../../../../src/core/models/services/api-models-service';
import { ProjectIdentifier } from '../../../../src/core/projects/core.interface';
import { createApiProjectService } from '../../../../src/core/projects/services/api-project-service';
import { ProjectSortingOptions } from '../../../../src/core/projects/services/project-service.interface';
import { createApiSupportedAlgorithmsService } from '../../../../src/core/supported-algorithms/services/api-supported-algorithms-service';
import { ServiceConfiguration } from '../../api-fixtures';
import { test } from '../../fixtures';
import { TestProject } from '../test-project';

function slugify(str: string) {
    str = str.replace(/^\s+|\s+$/g, ''); // trim leading/trailing white space
    str = str.toLowerCase(); // convert string to lowercase
    str = str
        .replace(/[^a-z0-9 -]/g, '') // remove any non-alphanumeric characters
        .replace(/\s+/g, '-') // replace spaces with hyphens
        .replace(/-+/g, '-'); // remove consecutive hyphens
    return str;
}

const pipeline = promisify(stream.pipeline);

async function extractTheStuff(
    destinationPath: string[],
    serviceConfiguration: ServiceConfiguration,
    projectIdentifier: ProjectIdentifier,
    ovmsPayload: {
        package_type: string;
        models: Array<{ model_group_id: string; model_id: string }>;
    }
) {
    const resultPath = path.resolve('./tests/results/geti-3');
    if (!fs.existsSync(resultPath)) {
        await mkdir(resultPath, { recursive: true });
    }

    const destinationFilePath = path.resolve(
        resultPath,
        `${destinationPath.join('-')}-${ovmsPayload.package_type}.zip`
    );
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

    const resultDestinationPath = path.resolve(resultPath, ...destinationPath);
    if (!fs.existsSync(resultDestinationPath)) {
        await mkdir(resultDestinationPath, { recursive: true });
    }

    try {
        const zip = new AdmZip(destinationFilePath);
        const extractedPath = path.resolve(resultDestinationPath, ovmsPayload.package_type);
        zip.extractAllTo(extractedPath);
    } catch (error) {
        console.error('Unable to unzip file', destinationFilePath, error);
    }
}

test.describe('Api testing', async () => {
    test.only('Downloading model export - deployment package', async ({
        apiServiceConfiguration,
        applicationServices,
    }) => {
        const testProject = new TestProject(apiServiceConfiguration);

        await test.step('Fetch workspace details', async () => {
            await testProject.getWorkspace();
        });

        const projectService = createApiProjectService(apiServiceConfiguration);
        const modelsService = createApiModelsService(apiServiceConfiguration);
        const supportedAlgorithmsService = createApiSupportedAlgorithmsService(apiServiceConfiguration);

        const workspaceIdentifier = testProject.workspaceIdentifier();

        const projectIds = [
            '68302dcf2af7ba4a0b2f5872', // yes we can
            '6821a412d5e1e5dc3bf200c1', // semantic card segmentation
            '5101e8f19d342b142b98535e', // kiemgetal
            '52ee42766e6b53b0df466c47', // aeromanas
            '68340c58c0f10881ffc9b190', // instance card segmentation 4 labels
            '6821a633d5e1e5dc3bf2021d', // rotated card detection
            '6836031160633ed43b454334', // card anomaly

            // '67b88889c3d4b31dec9ab03e',
            // '67b88923c3d4b31dec9ab1ca',
            // '67b88a9ec3d4b31dec9ab271',
            // '67b88c37c3d4b31dec9ab317',
            // '67b88d86c3d4b31dec9ab3bd',
            // '67b88e8fc3d4b31dec9ab463',
        ];

        async function downloadProject(projectId: string) {
            //console.log(`[${p.id}]: ${p.name}`);
            const projectIdentifier = { ...workspaceIdentifier, projectId };
            const project = await projectService.getProject(projectIdentifier);
            console.log(`[${project.id}] - ${project.name}`);

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

                        const destinationPath = [
                            slugify(project.name),
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

                        // if (!optimizedModel.modelName.includes('FP32')) {
                        //     continue;
                        // }
                        // if (optimizedModel.modelName.includes('with XAI')) {
                        //     continue;
                        // }
                        //console.log(destinationPath.join('-'));

                        // if (slugify(optimizedModel.modelName).includes('segnext')) {
                        //     await new Promise((resolve) => setTimeout(resolve, 30_000));

                        //     if (optimizedModel.modelName.toLocaleLowerCase().includes('fp16')) {
                        //         console.log('ignoring', destinationPath.join('-'));
                        //         continue;
                        //     }
                        // }

                        const getSdkPayload = {
                            package_type: 'geti_sdk',
                            models: [
                                {
                                    model_group_id: optimizedModelIdentifier.modelGroupId,
                                    model_id: optimizedModelIdentifier.optimizedModelId,
                                },
                            ],
                        };

                        //console.log(projectIdentifier, getSdkPayload);
                        //continue;

                        try {
                            await extractTheStuff(
                                destinationPath,
                                apiServiceConfiguration,
                                projectIdentifier,
                                getSdkPayload
                            );
                            await extractTheStuff(destinationPath, apiServiceConfiguration, projectIdentifier, {
                                ...getSdkPayload,
                                package_type: 'ovms',
                            });
                        } catch (e) {
                            console.error('Error while downloading model', e);
                        }
                    }
                }
            }
        }

        await Promise.all(projectIds.map(downloadProject));
        // for (const p of projectIds) {
        //     try {
        //         await downloadProject(p);
        //     } catch (e) {
        //         console.error(e, p);
        //     }
        // }
    });
});
