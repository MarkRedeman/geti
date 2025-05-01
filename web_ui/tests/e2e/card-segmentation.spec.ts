// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import fs from 'fs';

import { resolveDatasetPath } from '../utils/dataset';
import { withRelative } from '../utils/mouse';
import { expectProjectToHaveLabels, expectProjectToHaveType } from './../features/project-creation/expect';
import { expect } from './../fixtures/base-test';
import { test } from './fixtures';
import { loadCardAnnotations } from './utils';

test('Create card instance segmentation project', async ({
    createProjectPage,
    page,
    mediaPage,
    segmentAnythingTool,
}) => {
    await page.goto('/');

    await test.step('Create project', async () => {
        const label = 'Card';

        await page.getByRole('button', { name: /create new/i }).click();

        const projectPage = await createProjectPage.instanceSegmentation('Card instance segmentation', [label]);

        await expectProjectToHaveType(projectPage, 'Instance segmentation');
        await expectProjectToHaveLabels(projectPage, [label]);
    });

    await page.waitForTimeout(2000);

    const files: string[] = [];
    for (const suit of ['Hearts', 'Diamonds', 'Spades', 'Clubs']) {
        const path = resolveDatasetPath(`cards/${suit.toLocaleLowerCase()}`);
        files.push(...fs.readdirSync(path).map((filename) => resolveDatasetPath(path, filename)));
    }
    const totalFiles = files.length;

    await test.step('importing media', async () => {
        await page.getByRole('link', { name: /datasets/i }).click();

        const bucket = await mediaPage.getBucket();
        await bucket.uploadFiles(files);

        await expect(async () => {
            const message = page.getByText(new RegExp(`Uploaded ${totalFiles} of ${totalFiles} files`));
            await expect(message).toBeVisible();
        }).toPass({
            timeout: 1000 * 60 * 10,
        });
    });

    const cardAnnotations = loadCardAnnotations();
    await test.step(`Annotate ${totalFiles} images`, async () => {
        await page.getByRole('button', { name: /annotate interactively/i }).click();

        await expect(page.getByRole('contentinfo')).toBeVisible();

        for (let idx = 0; idx < totalFiles; idx++) {
            // Select the segment anything tool everytime so that it waits for
            // "Extracting image features" to have finished before continueing
            await segmentAnythingTool.selectTool();

            const contentinfo = page.getByRole('contentinfo');
            const fileInfo = (await contentinfo.getByLabel('media name').textContent()) ?? '';
            const filename = fileInfo.split(' (')[0];
            const cardAnnotation = cardAnnotations.find((image) => image.name === filename);

            // Remove any inference results
            await page.keyboard.press('Control+a');
            await page.keyboard.press('Delete');

            if (cardAnnotation) {
                const relative = await withRelative(page);

                for (const point of cardAnnotation.points) {
                    const { x, y } = relative(point.x, point.y);
                    await page.mouse.click(x, y);
                    await segmentAnythingTool.waitForResultShape();
                }
                const submitButton = page.getByRole('button', { name: /submit/i });
                await expect(submitButton).toBeEnabled();
            }

            const url = page.url();
            const nextItem = page.getByRole('button', { name: /next media item/i });

            if (await nextItem.isEnabled()) {
                const submitButton = page.getByRole('button', { name: /submit/i });

                await submitButton.click();
                await expect(page).not.toHaveURL(url);
            } else {
                const submitButton = page.getByRole('button', { name: /submit/i });
                if (await submitButton.isEnabled()) {
                    await submitButton.click();
                }

                break;
            }
        }
    });

    console.log('finished');
});

test('Create card segmentation project', async ({ createProjectPage, page, mediaPage, segmentAnythingTool }) => {
    await page.goto('/');

    await test.step('Create project', async () => {
        const label = 'Card';

        await page.getByRole('button', { name: /create new/i }).click();

        const projectPage = await createProjectPage.segmentation('Card segmentation', [label]);

        await expectProjectToHaveType(projectPage, 'Segmentation');
        await expectProjectToHaveLabels(projectPage, [label]);
    });

    await page.waitForTimeout(2000);

    const files: string[] = [];
    for (const suit of ['Hearts', 'Diamonds', 'Spades', 'Clubs']) {
        const path = resolveDatasetPath(`cards/${suit.toLocaleLowerCase()}`);
        files.push(...fs.readdirSync(path).map((filename) => resolveDatasetPath(path, filename)));
    }
    const totalFiles = files.length;

    await test.step('importing media', async () => {
        await page.getByRole('link', { name: /datasets/i }).click();

        const bucket = await mediaPage.getBucket();
        await bucket.uploadFiles(files);

        await expect(async () => {
            const message = page.getByText(new RegExp(`Uploaded ${totalFiles} of ${totalFiles} files`));
            await expect(message).toBeVisible();
        }).toPass({
            timeout: 1000 * 60 * 10,
        });
    });

    const cardAnnotations = loadCardAnnotations();
    await test.step(`Annotate ${totalFiles} images`, async () => {
        await page.getByRole('button', { name: /annotate interactively/i }).click();

        await expect(page.getByRole('contentinfo')).toBeVisible();

        for (let idx = 0; idx < totalFiles; idx++) {
            // Select the segment anything tool everytime so that it waits for
            // "Extracting image features" to have finished before continueing
            await segmentAnythingTool.selectTool();

            const contentinfo = page.getByRole('contentinfo');
            const fileInfo = (await contentinfo.getByLabel('media name').textContent()) ?? '';
            const filename = fileInfo.split(' (')[0];
            const cardAnnotation = cardAnnotations.find((image) => image.name === filename);

            console.log(filename);

            // Remove any inference results
            await page.keyboard.press('Control+a');
            await page.keyboard.press('Delete');

            if (cardAnnotation) {
                const relative = await withRelative(page);

                for (const point of cardAnnotation.points) {
                    const { x, y } = relative(point.x, point.y);
                    await page.mouse.click(x, y);
                    await segmentAnythingTool.waitForResultShape();
                }
                const submitButton = page.getByRole('button', { name: /submit/i });
                await expect(submitButton).toBeEnabled();
            }

            const url = page.url();
            const nextItem = page.getByRole('button', { name: /next media item/i });

            if (await nextItem.isEnabled()) {
                const submitButton = page.getByRole('button', { name: /submit/i });

                await submitButton.click();
                await expect(page).not.toHaveURL(url);
            } else {
                const submitButton = page.getByRole('button', { name: /submit/i });
                if (await submitButton.isEnabled()) {
                    await submitButton.click();
                }

                break;
            }
        }
    });

    console.log('finished');
});

test('Create card oriented detection project', async ({ createProjectPage, page, mediaPage, segmentAnythingTool }) => {
    await page.goto('/');

    await test.step('Create project', async () => {
        const label = 'Card';

        await page.getByRole('button', { name: /create new/i }).click();

        const projectPage = await createProjectPage.orientedDetection('Card rotated detection', [label]);

        await expectProjectToHaveType(projectPage, 'Detection oriented');
        await expectProjectToHaveLabels(projectPage, [label]);
    });

    await page.waitForTimeout(2000);

    const files: string[] = [];
    for (const suit of ['Hearts', 'Diamonds', 'Spades', 'Clubs']) {
        const path = resolveDatasetPath(`cards/${suit.toLocaleLowerCase()}`);
        files.push(...fs.readdirSync(path).map((filename) => resolveDatasetPath(path, filename)));
    }
    const totalFiles = files.length;

    await test.step('importing media', async () => {
        await page.getByRole('link', { name: /datasets/i }).click();

        const bucket = await mediaPage.getBucket();
        await bucket.uploadFiles(files);

        await expect(async () => {
            const message = page.getByText(new RegExp(`Uploaded ${totalFiles} of ${totalFiles} files`));
            await expect(message).toBeVisible();
        }).toPass({
            timeout: 1000 * 60 * 10,
        });
    });

    const cardAnnotations = loadCardAnnotations();
    await test.step(`Annotate ${totalFiles} images`, async () => {
        await page.getByRole('button', { name: /annotate interactively/i }).click();

        await expect(page.getByRole('contentinfo')).toBeVisible();

        for (let idx = 0; idx < totalFiles; idx++) {
            // Select the segment anything tool everytime so that it waits for
            // "Extracting image features" to have finished before continueing
            await segmentAnythingTool.selectTool();

            const contentinfo = page.getByRole('contentinfo');
            const fileInfo = (await contentinfo.getByLabel('media name').textContent()) ?? '';
            const filename = fileInfo.split(' (')[0];
            const cardAnnotation = cardAnnotations.find((image) => image.name === filename);

            console.log(filename);

            // Remove any inference results
            await page.keyboard.press('Control+a');
            await page.keyboard.press('Delete');

            if (cardAnnotation) {
                const relative = await withRelative(page);

                for (const point of cardAnnotation.points) {
                    const { x, y } = relative(point.x, point.y);
                    await page.mouse.click(x, y);
                    await segmentAnythingTool.waitForResultShape();
                }
                const submitButton = page.getByRole('button', { name: /submit/i });
                await expect(submitButton).toBeEnabled();
            }

            const url = page.url();
            const nextItem = page.getByRole('button', { name: /next media item/i });

            if (await nextItem.isEnabled()) {
                const submitButton = page.getByRole('button', { name: /submit/i });

                await submitButton.click();
                await expect(page).not.toHaveURL(url);
            } else {
                const submitButton = page.getByRole('button', { name: /submit/i });
                if (await submitButton.isEnabled()) {
                    await submitButton.click();
                }

                break;
            }
        }
    });

    console.log('finished');
});

test('Create card detection project', async ({ createProjectPage, page, mediaPage, segmentAnythingTool }) => {
    await page.goto('/');

    await test.step('Create project', async () => {
        const label = 'Card';

        await page.getByRole('button', { name: /create new/i }).click();

        const projectPage = await createProjectPage.detection('Card detection', [label]);

        await expectProjectToHaveType(projectPage, 'Detection');
        await expectProjectToHaveLabels(projectPage, [label]);
    });

    await page.waitForTimeout(2000);

    const files: string[] = [];
    for (const suit of ['Hearts', 'Diamonds', 'Spades', 'Clubs']) {
        const path = resolveDatasetPath(`cards/${suit.toLocaleLowerCase()}`);
        files.push(...fs.readdirSync(path).map((filename) => resolveDatasetPath(path, filename)));
    }
    const totalFiles = files.length;

    await test.step('importing media', async () => {
        await page.getByRole('link', { name: /datasets/i }).click();

        const bucket = await mediaPage.getBucket();
        await bucket.uploadFiles(files);

        await expect(async () => {
            const message = page.getByText(new RegExp(`Uploaded ${totalFiles} of ${totalFiles} files`));
            await expect(message).toBeVisible();
        }).toPass({
            timeout: 1000 * 60 * 10,
        });
    });

    const cardAnnotations = loadCardAnnotations();
    await test.step(`Annotate ${totalFiles} images`, async () => {
        await page.getByRole('button', { name: /annotate interactively/i }).click();

        await expect(page.getByRole('contentinfo')).toBeVisible();

        for (let idx = 0; idx < totalFiles; idx++) {
            // Select the segment anything tool everytime so that it waits for
            // "Extracting image features" to have finished before continueing
            await segmentAnythingTool.selectTool();

            const contentinfo = page.getByRole('contentinfo');
            const fileInfo = (await contentinfo.getByLabel('media name').textContent()) ?? '';
            const filename = fileInfo.split(' (')[0];
            const cardAnnotation = cardAnnotations.find((image) => image.name === filename);

            console.log(filename);

            // Remove any inference results
            await page.keyboard.press('Control+a');
            await page.keyboard.press('Delete');

            if (cardAnnotation) {
                const relative = await withRelative(page);

                for (const point of cardAnnotation.points) {
                    const { x, y } = relative(point.x, point.y);
                    await page.mouse.click(x, y);
                    await segmentAnythingTool.waitForResultShape();
                }
                const submitButton = page.getByRole('button', { name: /submit/i });
                await expect(submitButton).toBeEnabled();
            }

            const url = page.url();
            const nextItem = page.getByRole('button', { name: /next media item/i });

            if (await nextItem.isEnabled()) {
                const submitButton = page.getByRole('button', { name: /submit/i });

                await submitButton.click();
                await expect(page).not.toHaveURL(url);
            } else {
                const submitButton = page.getByRole('button', { name: /submit/i });
                if (await submitButton.isEnabled()) {
                    await submitButton.click();
                }

                break;
            }
        }
    });

    console.log('finished');
});
