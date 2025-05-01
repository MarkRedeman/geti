// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import { MEDIA_GROUP } from '../../../src/core/media/base-media.interface';
import { getMediaItemFromDTO } from '../../../src/core/media/services/utils';
import {
    getSubsetMediaFilter,
    Subset,
} from '../../../src/pages/project-details/components/project-model/training-dataset/utils';
import { test } from '../fixtures';
import { TestProject } from './test-project';

const SUBSETS = [Subset.TRAINING, Subset.VALIDATION, Subset.TESTING];

const configuration = {
    projectId: '677bd98d178f0fbc88679d5c',
    groupId: '677bd98d178f0fbc88679d60',
    modelId: '677be004a75d282010d43fc1',
};

test('Create a testing set from a models testing set', async ({ apiServiceConfiguration, applicationServices }) => {
    const { projectService, modelsService, trainingDatasetService, annotationService } = applicationServices;
    const testProject = new TestProject(apiServiceConfiguration);

    await test.step('Fetch workspace details', async () => {
        await testProject.getWorkspace();
    });

    testProject.projectId = configuration.projectId;
    const projectIdentifier = testProject.projectIdentifier();
    const project = await projectService.getProject(projectIdentifier);

    const model = await modelsService.getModel({
        ...projectIdentifier,
        groupId: configuration.groupId,
        modelId: configuration.modelId,
    });

    for (const subset of SUBSETS) {
        const dataset = await projectService.createDataset({
            name: `${subset} - ${model.trainedModel.modelName} - v${model.trainedModel.version} `,
            projectIdentifier,
        });
        const datasetIdentifier = { ...projectIdentifier, datasetId: dataset.id };

        await test.step(`Copy ${subset} set`, async () => {
            const datasetStorageId = model.trainingDatasetInfo.storageId;
            const datasetRevisionId = model.trainingDatasetInfo.revisionId;
            const dataset = await trainingDatasetService.getTrainingDatasetMediaAdvancedFilter(
                projectIdentifier,
                datasetStorageId,
                datasetRevisionId,
                1000,
                null,
                getSubsetMediaFilter(subset),
                {}
            );

            for (const media of dataset.media) {
                await test.step(`${media.name}`, async () => {
                    console.log('Get annotations');
                    const annotations = await annotationService.getAnnotations(
                        {
                            ...projectIdentifier,
                            datasetId: datasetStorageId,
                        },
                        project.labels,
                        media
                    );

                    // Download image
                    const imageSrc = apiServiceConfiguration.router.PREFIX(media.src);
                    console.log('Downloading image', { imageSrc });

                    const { data: stream } = await apiServiceConfiguration.instance.get(imageSrc, {
                        responseType: 'stream',
                    });

                    console.log('Uploading image into dataset', { imageSrc });
                    console.log(stream);
                    // Uplaod image into dataset
                    const formData = new FormData();
                    formData.append('file', new Blob([stream]), `${media.name}.png`);

                    const result = await apiServiceConfiguration.instance.post(
                        apiServiceConfiguration.router.MEDIA_UPLOAD(datasetIdentifier, MEDIA_GROUP.IMAGES),
                        formData,
                        { headers: { 'content-type': 'multipart/form-data' } }
                    );

                    // TODO
                    const mediaItem = getMediaItemFromDTO(
                        datasetIdentifier,
                        result.data,
                        apiServiceConfiguration.router
                    );

                    // Apply annotation to image

                    console.log('uplaoding annotaitons');
                    await annotationService.saveAnnotations(datasetIdentifier, mediaItem, annotations);
                });
            }
        });
    }
});
