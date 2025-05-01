// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import { withRelative } from '../utils/mouse';
import { expectProjectToHaveLabels, expectProjectToHaveType } from './../features/project-creation/expect';
import { expect } from './../fixtures/base-test';
import { test } from './fixtures';
import { getFishVideoFiles, loadFishAnnotations, VideoAnnotations } from './utils';

// The amount of annotations is picked so that Geti could start training 5 times (each round requiring 12 annotations)
const AMOUNT_OF_ANNOTATIONS = 4 * 12;

test('Create fish segmentation project', async ({
    createProjectPage,
    page,
    mediaPage,
    interactiveSegmentationTool,
    labelShortcutsPage,
}) => {
    const screen = page;
    await test.step('Create project', async () => {
        const detectionLabel = 'Fish';

        await (await screen.findByRole('button', { name: /create new/i })).click();

        const projectPage = await createProjectPage.segmentation('Fish segmentation', [detectionLabel]);

        const labels = [detectionLabel];

        await expectProjectToHaveType(projectPage, 'Segmentation');
        await expectProjectToHaveLabels(projectPage, labels);
    });

    await test.step('importing media', async () => {
        await page.getByRole('link', { name: /datasets/i }).click();

        const bucket = await mediaPage.getBucket();

        const files = getFishVideoFiles();
        await bucket.uploadFiles(files);

        await expect(async () => {
            await expect(await screen.findByText(/0 images, 5 videos/i)).toBeVisible();
        }).toPass({
            timeout: 1000 * 60 * 10,
        });
    });

    await test.step(`Annotate ${AMOUNT_OF_ANNOTATIONS} frames`, async () => {
        await (await screen.findByRole('button', { name: /annotate interactively/i })).click();

        const videoAnnotations: VideoAnnotations = {};

        await expect(await screen.findByRole('contentinfo')).toBeVisible();
        await screen.waitForTimeout(5000);
        await interactiveSegmentationTool.selectTool();
        await interactiveSegmentationTool.toggleDynamicSelectionMode();

        for (let idx = 0; idx < 5 * 12; idx++) {
            // In annotator find the filename
            await expect(page.getByRole('contentinfo')).toBeVisible();
            const fileInfo = (await contentinfo.getByLabel('media name').textContent()) ?? '';
            const filename = fileInfo.split(' (')[0];
            const currentlySelectedFrame =
                (await screen.getByLabelText('Currently selected frame number').textContent()) ?? '';
            const matchFrameNumber = currentlySelectedFrame.match(/current frame (\d+)/);
            const frameNumber = Number(matchFrameNumber?.at(1));
            console.log(filename, frameNumber);

            loadFishAnnotations(filename, videoAnnotations);

            const annotations = videoAnnotations[filename][frameNumber];
            await screen.keyboard.press('Control+a');
            await screen.keyboard.press('Delete');

            if (annotations.length === 0) {
                (await labelShortcutsPage.getPinnedLabelLocator('Empty')).click();
            }

            for (const annotation of annotations) {
                if (annotation.labels.some((label) => label === 'Diver')) {
                    continue;
                }

                const shape = annotation.shape;
                if (shape.width <= 5 || shape.height <= 5) {
                    continue;
                }

                await interactiveSegmentationTool.drawBoundingBox(shape);

                const relative = await withRelative(screen);
                const point = relative(
                    Math.max(0.1, shape.x + shape.width / 2),
                    Math.max(0.1, shape.y + shape.height / 2)
                );
                await screen.mouse.click(point.x, point.y);

                await (await screen.findByRole('button', { name: 'accept ritm annotation' })).click();

                // Deselect the annotation so that when we draw the new annotation we don't press on the "Edit label" button
                await screen.keyboard.press('Control+d');
            }

            const url = screen.url();
            await screen.getByRole('button', { name: /submit annotations/i }).click();
            await expect(() => expect(url).not.toEqual(screen.url())).toPass();
        }
    });

    console.log('finished');
});

test('Create fish instance segmentation project', async ({
    createProjectPage,
    page,
    mediaPage,
    interactiveSegmentationTool,
    labelShortcutsPage,
}) => {
    const screen = page;
    await test.step('Create project', async () => {
        const detectionLabel = 'Fish';

        await (await screen.findByRole('button', { name: /create new/i })).click();

        const projectPage = await createProjectPage.instanceSegmentation('Fish segmentation', [detectionLabel]);

        const labels = [detectionLabel];

        await expectProjectToHaveType(projectPage, 'Instance segmentation');
        await expectProjectToHaveLabels(projectPage, labels);
    });

    await test.step('importing media', async () => {
        await page.getByRole('link', { name: /datasets/i }).click();

        const bucket = await mediaPage.getBucket();

        const files = getFishVideoFiles();
        await bucket.uploadFiles(files);

        await expect(async () => {
            await expect(await screen.findByText(/0 images, 5 videos/i)).toBeVisible();
        }).toPass({
            timeout: 1000 * 60 * 10,
        });
    });

    await test.step(`Annotate ${AMOUNT_OF_ANNOTATIONS} frames`, async () => {
        await (await screen.findByRole('button', { name: /annotate interactively/i })).click();

        const videoAnnotations: VideoAnnotations = {};

        await expect(page.getByRole('contentinfo')).toBeVisible();
        await screen.waitForTimeout(5000);
        await interactiveSegmentationTool.selectTool();
        await interactiveSegmentationTool.toggleDynamicSelectionMode();

        for (let idx = 0; idx < 5 * 12; idx++) {
            // In annotator find the filename
            const contentinfo = await screen.findByRole('contentinfo');
            const fileInfo = (await contentinfo.getByLabel('media name').textContent()) ?? '';
            const filename = fileInfo.split(' (')[0];
            const currentlySelectedFrame =
                (await screen.getByLabelText('Currently selected frame number').textContent()) ?? '';
            const matchFrameNumber = currentlySelectedFrame.match(/current frame (\d+)/);
            const frameNumber = Number(matchFrameNumber?.at(1));
            console.log(filename, frameNumber);

            loadFishAnnotations(filename, videoAnnotations);

            const annotations = videoAnnotations[filename][frameNumber];
            await screen.keyboard.press('Control+a');
            await screen.keyboard.press('Delete');

            if (annotations.length === 0) {
                (await labelShortcutsPage.getPinnedLabelLocator('Empty')).click();
            }

            for (const annotation of annotations) {
                if (annotation.labels.some((label) => label === 'Diver')) {
                    continue;
                }

                const shape = annotation.shape;
                if (shape.width <= 5 || shape.height <= 5) {
                    continue;
                }

                await interactiveSegmentationTool.drawBoundingBox(shape);

                const relative = await withRelative(screen);
                const point = relative(
                    Math.max(0.1, shape.x + shape.width / 2),
                    Math.max(0.1, shape.y + shape.height / 2)
                );
                await screen.mouse.click(point.x, point.y);

                await (await screen.findByRole('button', { name: 'accept ritm annotation' })).click();

                // Deselect the annotation so that when we draw the new annotation we don't press on the "Edit label" button
                await screen.keyboard.press('Control+d');
            }

            const url = screen.url();
            await screen.getByRole('button', { name: /submit annotations/i }).click();
            await expect(() => expect(url).not.toEqual(screen.url())).toPass();
        }
    });

    console.log('finished');
});
