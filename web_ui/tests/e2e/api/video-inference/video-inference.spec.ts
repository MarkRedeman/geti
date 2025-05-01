// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import { expect } from '@playwright/test';

import { Annotation } from '../../../../src/core/annotations/annotation.interface';
import {
    PredictionCache,
    PredictionMode,
} from '../../../../src/core/annotations/services/prediction-service.interface';
import { MEDIA_TYPE } from '../../../../src/core/media/base-media.interface';
import { MediaIdentifier } from '../../../../src/core/media/media.interface';
import { isVideo, isVideoFrame } from '../../../../src/core/media/video.interface';
import { test } from '../../fixtures';
import { TestProject } from '../test-project';

const cartoonFish = {
    organizationId: 'cd26f054-fda8-487b-b089-ba87a5f352d8',
    workspaceId: '024d7600-908d-499b-93ab-fb4d2e2eb9c9',
    projectId: '6784fb2fc9353eba412ce44c',
    datasetId: '6784fb2fc9353eba412ce452',
    videoId: '6784fb3ac9353eba412ce45c',
};

const configuration = cartoonFish;

test('Compare video batch inference vs single inference', async ({
    apiServiceConfiguration,
    applicationServices: { projectService, inferenceService, mediaService },
}) => {
    const testProject = new TestProject(apiServiceConfiguration);

    await test.step('Fetch workspace details', async () => {
        await testProject.getWorkspace();
    });

    testProject.projectId = configuration.projectId;

    const projectIdentifier = testProject.projectIdentifier();
    const project = await projectService.getProject(projectIdentifier);
    const datasetIdentifier = {
        ...projectIdentifier,
        datasetId: project.datasets[0].id,
    };

    const mediaItemId: MediaIdentifier = {
        type: MEDIA_TYPE.VIDEO_FRAME,
        videoId: configuration.videoId,
        frameNumber: 0,
    };

    const videoFrame = await mediaService.getMediaItem(datasetIdentifier, mediaItemId);
    const video = await mediaService.getMediaItem(datasetIdentifier, {
        type: MEDIA_TYPE.VIDEO,
        videoId: configuration.videoId,
    });

    if (!isVideoFrame(videoFrame)) {
        throw new Error('Did not receive a videoframe from media service');
    }

    if (!isVideo(video)) {
        throw new Error('Did not receive a video from media service');
    }

    const videoPredictions = await inferenceService.getVideoPredictions(
        datasetIdentifier,
        project.labels,
        videoFrame,
        PredictionMode.ONLINE,
        {
            startFrame: 0,
            endFrame: 239,
            frameSkip: 12,
        }
    );

    // For each batch inference prediction compare it with the single inference predictions
    for (const frameNumberKey of Object.keys(videoPredictions)) {
        const frameNumber = Number(frameNumberKey);

        await test.step(`${frameNumber}`, async () => {
            const videoFrame = await mediaService.getMediaItem(datasetIdentifier, {
                ...mediaItemId,
                frameNumber,
            });

            if (!isVideoFrame(videoFrame)) {
                console.log('not video frame', frameNumber);
                return;
            }

            const predictions = await inferenceService.getPredictions(
                datasetIdentifier,
                project.labels,
                videoFrame,
                PredictionCache.NEVER
            );

            const compareByShape = ({ shape }: Annotation) => ({ shape });
            const singlePrediction = predictions.map(compareByShape);
            const batchPredictons = videoPredictions[frameNumber].map(compareByShape);

            expect.soft(singlePrediction).toEqual(batchPredictons);
        });
    }
});
