// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import fs from 'fs';

import { v4 as uuidv4 } from 'uuid';

import { DatasetTabActions } from '../../../src/pages/project-details/components/project-dataset/utils';
import { resolveDatasetPath } from '../../utils/dataset';
import { withRelative } from '../../utils/mouse';
import { loadCardAnnotations } from '../utils';
import { expectProjectToHaveLabels, expectProjectToHaveType } from './../../features/project-creation/expect';
import { expect } from './../../fixtures/base-test';
import { test } from './../fixtures';
import { TIMEOUTS } from './timeouts';

test(
    'Simple Card Instance Segmentation',
    { tag: ['@daily'] },
    async ({ workspacesPage, page, mediaPage, projectPage, datasetPage, annotatorPage, segmentAnythingTool }) => {
        await page.goto('/');

        const uniqueSuffix = uuidv4();
        const projectName = `Card instance segmentation - [${uniqueSuffix}]`;

        const label = 'Card';

        await test.step('create project', async () => {
            const createProjectPage = await workspacesPage.createProject();

            const cardProjectPage = await createProjectPage.instanceSegmentation(projectName, [label]);

            await test.step('Verify project was created succesfully', async () => {
                await expectProjectToHaveType(cardProjectPage, 'Instance segmentation');
                await expectProjectToHaveLabels(cardProjectPage, [label]);
            });
        });

        const files: string[] = [];
        for (const suit of ['Hearts', 'Diamonds', 'Spades', 'Clubs']) {
            const path = resolveDatasetPath(`cards/${suit.toLocaleLowerCase()}`);
            files.push(...fs.readdirSync(path).map((filename) => resolveDatasetPath(path, filename)));
        }
        const totalFiles = files.length;

        await test.step('importing media', async () => {
            await projectPage.goToDatasetPage();

            const bucket = await mediaPage.getBucket();
            await bucket.uploadFiles(files);

            await expect(page.getByText(new RegExp(`Uploaded ${totalFiles} of ${totalFiles} files`))).toBeVisible({
                timeout: TIMEOUTS.uploadMedia,
            });

            await bucket.expectTotalMedia({ images: totalFiles });
        });

        const cardAnnotations = loadCardAnnotations();
        const AMOUNT_OF_ANNOTATIONS = 12; // totalFiles
        await test.step(`Annotate ${AMOUNT_OF_ANNOTATIONS} images`, async () => {
            await page.getByRole('button', { name: /annotate interactively/i }).click();

            await expect(page.getByRole('contentinfo')).toBeVisible();

            for (let idx = 0; idx < AMOUNT_OF_ANNOTATIONS; idx++) {
                // Select the segment anything tool everytime so that it waits for
                // "Extracting image features" to have finished before continueing
                await segmentAnythingTool.selectTool();

                const filename = await annotatorPage.selectedMediaFilename();
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
                await annotatorPage.submit();
                await expect(page).not.toHaveURL(url);
            }

            await annotatorPage.goBackToProjectPage();
        });

        await test.step('importing dataset', async () => {
            const datasetZipPath = resolveDatasetPath('cards/test-card-semantic-segmentation-dataset.zip');
            const datasetName = 'Testing set 1';

            // Create new testing set and open the import dataset dialog
            await datasetPage.createDataset();

            const importDatasetDialogPage = await datasetPage.selectDatasetTabMenuItem(
                datasetName,
                DatasetTabActions.ImportDataset
            );

            // Upload the dataset
            await importDatasetDialogPage.uploadDataset(datasetZipPath);

            const timeout = TIMEOUTS.importDataset;
            await page.getByRole('button', { name: /import/i }).click({ timeout });

            // Wait for the progress to start
            await expect(page.getByText(/Import dataset to project/)).toBeVisible({ timeout });
            await expect(page.getByText(/Waiting.../)).toBeVisible({ timeout });
        });

        await test.step('wait for import & training jobs to finish', async () => {
            // Open jobs dialog
            await page.getByLabel('Jobs in progress').click();

            // Select our project
            await page.getByLabel(/Job scheduler filter project/).fill(projectName);
            await page.getByRole('option', { name: projectName }).click();

            // Verify that the job is running
            await expect(page.getByLabel('action-link')).toHaveCount(2); // Training + import jobs

            await page.getByRole('tab', { name: 'Finished jobs' }).click();

            // Wait for the job to finish
            await test.step('import job', async () => {
                await expect(
                    page.getByLabel('action-link').getByText('Import Dataset to Existing Project')
                ).toBeVisible({
                    timeout: TIMEOUTS.importDataset,
                });
            });

            // Wait for training to finish
            await test.step('training job', async () => {
                await expect(page.getByLabel('action-link').getByText('Training')).toBeVisible({
                    timeout: TIMEOUTS.training,
                });
            });

            // Close the dialog
            await page.keyboard.press('Escape');
        });

        await test.step('run a test on imported dataset', async () => {
            // Verify that we have an active model
            const modelsPage = await projectPage.goToModelsPage();

            // Run test on ative model's FP16 version
            const activeModel = { name: 'MaskRCNN-EfficientNetB2B', version: '1' };
            const modelPage = await modelsPage.goToModel(activeModel.name, activeModel.version);
            const runTestDialogPage = await modelPage.openTestDialog(`${activeModel.name} OpenVINO FP16`);

            // Run and inspect tests
            const testName = `Test`;
            await runTestDialogPage.configureTest({ dataset: 'Testing set 1', testName });
            await runTestDialogPage.runTest();

            const testsPage = await modelsPage.seeTestProgress();

            await test.step('Wait for test to finish', async () => {
                await testsPage.waitForTestToFinish(testName);
            });

            const testPage = await testsPage.gotoTest(testName);
            const score = await testPage.getScore();

            // The model should be better than throwing coins
            expect(score).toBeGreaterThanOrEqual(25);
        });
    }
);

test(
    'Simple Card Semantic Segmentation',
    { tag: ['@daily'] },
    async ({ workspacesPage, page, mediaPage, projectPage, datasetPage, annotatorPage, segmentAnythingTool }) => {
        await page.goto('/');

        const uniqueSuffix = uuidv4();
        const projectName = `Card semantic segmentation - [${uniqueSuffix}]`;

        const label = 'Card';

        await test.step('create project', async () => {
            const createProjectPage = await workspacesPage.createProject();

            const cardProjectPage = await createProjectPage.segmentation(projectName, [label]);

            await test.step('Verify project was created succesfully', async () => {
                await expectProjectToHaveType(cardProjectPage, 'Segmentation');
                await expectProjectToHaveLabels(cardProjectPage, [label]);
            });
        });

        const files: string[] = [];
        for (const suit of ['Hearts', 'Diamonds', 'Spades', 'Clubs']) {
            const path = resolveDatasetPath(`cards/${suit.toLocaleLowerCase()}`);
            files.push(...fs.readdirSync(path).map((filename) => resolveDatasetPath(path, filename)));
        }
        const totalFiles = files.length;

        await test.step('importing media', async () => {
            await projectPage.goToDatasetPage();

            const bucket = await mediaPage.getBucket();
            await bucket.uploadFiles(files);

            await expect(page.getByText(new RegExp(`Uploaded ${totalFiles} of ${totalFiles} files`))).toBeVisible({
                timeout: TIMEOUTS.uploadMedia,
            });

            await bucket.expectTotalMedia({ images: totalFiles });
        });

        const cardAnnotations = loadCardAnnotations();
        const AMOUNT_OF_ANNOTATIONS = 12; // totalFiles
        await test.step(`Annotate ${AMOUNT_OF_ANNOTATIONS} images`, async () => {
            await page.getByRole('button', { name: /annotate interactively/i }).click();

            await expect(page.getByRole('contentinfo')).toBeVisible();

            for (let idx = 0; idx < AMOUNT_OF_ANNOTATIONS; idx++) {
                // Select the segment anything tool everytime so that it waits for
                // "Extracting image features" to have finished before continueing
                await segmentAnythingTool.selectTool();

                const filename = await annotatorPage.selectedMediaFilename();
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
                await annotatorPage.submit();
                await expect(page).not.toHaveURL(url);
            }

            await annotatorPage.goBackToProjectPage();
        });

        await test.step('importing dataset', async () => {
            const datasetZipPath = resolveDatasetPath('cards/test-card-semantic-segmentation-dataset.zip');
            const datasetName = 'Testing set 1';

            // Create new testing set and open the import dataset dialog
            await datasetPage.createDataset();

            const importDatasetDialogPage = await datasetPage.selectDatasetTabMenuItem(
                datasetName,
                DatasetTabActions.ImportDataset
            );

            // Upload the dataset
            await importDatasetDialogPage.uploadDataset(datasetZipPath);

            const timeout = TIMEOUTS.importDataset;
            await page.getByRole('button', { name: /import/i }).click({ timeout });

            // Wait for the progress to start
            await expect(page.getByText(/Import dataset to project/)).toBeVisible({ timeout });
            await expect(page.getByText(/Waiting.../)).toBeVisible({ timeout });
        });

        await test.step('wait for import & training jobs to finish', async () => {
            // Open jobs dialog
            await page.getByLabel('Jobs in progress').click();

            // Select our project
            await page.getByLabel(/Job scheduler filter project/).fill(projectName);
            await page.getByRole('option', { name: projectName }).click();

            // Verify that the job is running
            await expect(page.getByLabel('action-link')).toHaveCount(2); // Training + import jobs

            await page.getByRole('tab', { name: 'Finished jobs' }).click();

            // Wait for the job to finish
            await test.step('import job', async () => {
                await expect(
                    page.getByLabel('action-link').getByText('Import Dataset to Existing Project')
                ).toBeVisible({
                    timeout: TIMEOUTS.importDataset,
                });
            });

            // Wait for training to finish
            await test.step('training job', async () => {
                await expect(page.getByLabel('action-link').getByText('Training')).toBeVisible({
                    timeout: TIMEOUTS.training,
                });
            });

            // Close the dialog
            await page.keyboard.press('Escape');
        });

        await test.step('run a test on imported dataset', async () => {
            // Verify that we have an active model
            const modelsPage = await projectPage.goToModelsPage();

            // Run test on ative model's FP16 version
            const activeModel = { name: 'Lite-HRNet-18-mod2', version: '1' };
            const modelPage = await modelsPage.goToModel(activeModel.name, activeModel.version);
            const runTestDialogPage = await modelPage.openTestDialog(`${activeModel.name} OpenVINO FP16`);

            // Run and inspect tests
            const testName = `Test`;
            await runTestDialogPage.configureTest({ dataset: 'Testing set 1', testName });
            await runTestDialogPage.runTest();

            const testsPage = await modelsPage.seeTestProgress();

            await test.step('Wait for test to finish', async () => {
                await testsPage.waitForTestToFinish(testName);
            });

            const testPage = await testsPage.gotoTest(testName);
            const score = await testPage.getScore();

            // The model should be better than throwing coins
            expect(score).toBeGreaterThanOrEqual(25);
        });
    }
);

test(
    'Simple Card Rotated Detection',
    { tag: ['@daily'] },
    async ({ workspacesPage, page, mediaPage, projectPage, datasetPage, annotatorPage, segmentAnythingTool }) => {
        await page.goto('/');

        const uniqueSuffix = uuidv4();
        const projectName = `Rotated card detection - [${uniqueSuffix}]`;

        const label = 'Card';

        await test.step('create project', async () => {
            const createProjectPage = await workspacesPage.createProject();

            const cardProjectPage = await createProjectPage.orientedDetection(projectName, [label]);

            await test.step('Verify project was created succesfully', async () => {
                await expectProjectToHaveType(cardProjectPage, 'Detection oriented');
                await expectProjectToHaveLabels(cardProjectPage, [label]);
            });
        });

        const files: string[] = [];
        for (const suit of ['Hearts', 'Diamonds', 'Spades', 'Clubs']) {
            const path = resolveDatasetPath(`cards/${suit.toLocaleLowerCase()}`);
            files.push(...fs.readdirSync(path).map((filename) => resolveDatasetPath(path, filename)));
        }
        const totalFiles = files.length;

        await test.step('importing media', async () => {
            await projectPage.goToDatasetPage();

            const bucket = await mediaPage.getBucket();
            await bucket.uploadFiles(files);

            await expect(page.getByText(new RegExp(`Uploaded ${totalFiles} of ${totalFiles} files`))).toBeVisible({
                timeout: TIMEOUTS.uploadMedia,
            });

            await bucket.expectTotalMedia({ images: totalFiles });
        });

        const cardAnnotations = loadCardAnnotations();
        const AMOUNT_OF_ANNOTATIONS = 12; // totalFiles
        await test.step(`Annotate ${AMOUNT_OF_ANNOTATIONS} images`, async () => {
            await page.getByRole('button', { name: /annotate interactively/i }).click();

            await expect(page.getByRole('contentinfo')).toBeVisible();

            for (let idx = 0; idx < AMOUNT_OF_ANNOTATIONS; idx++) {
                // Select the segment anything tool everytime so that it waits for
                // "Extracting image features" to have finished before continueing
                await segmentAnythingTool.selectTool();

                const filename = await annotatorPage.selectedMediaFilename();
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
                await annotatorPage.submit();
                await expect(page).not.toHaveURL(url);
            }

            await annotatorPage.goBackToProjectPage();
        });

        await test.step('importing dataset', async () => {
            const datasetZipPath = resolveDatasetPath('cards/test-rotated-card-detection-dataset.zip');
            const datasetName = 'Testing set 1';

            // Create new testing set and open the import dataset dialog
            await datasetPage.createDataset();

            const importDatasetDialogPage = await datasetPage.selectDatasetTabMenuItem(
                datasetName,
                DatasetTabActions.ImportDataset
            );

            // Upload the dataset
            await importDatasetDialogPage.uploadDataset(datasetZipPath);

            const timeout = TIMEOUTS.importDataset;
            await page.getByRole('button', { name: /import/i }).click({ timeout });

            // Wait for the progress to start
            await expect(page.getByText(/Import dataset to project/)).toBeVisible({ timeout });
            await expect(page.getByText(/Waiting.../)).toBeVisible({ timeout });
        });

        await test.step('wait for import & training jobs to finish', async () => {
            // Open jobs dialog
            await page.getByLabel('Jobs in progress').click();

            // Select our project
            await page.getByLabel(/Job scheduler filter project/).fill(projectName);
            await page.getByRole('option', { name: projectName }).click();

            // Verify that the job is running
            await expect(page.getByLabel('action-link')).toHaveCount(2); // Training + import jobs

            await page.getByRole('tab', { name: 'Finished jobs' }).click();

            // Wait for the job to finish
            await test.step('import job', async () => {
                await expect(
                    page.getByLabel('action-link').getByText('Import Dataset to Existing Project')
                ).toBeVisible({
                    timeout: TIMEOUTS.importDataset,
                });
            });

            // Wait for training to finish
            await test.step('training job', async () => {
                await expect(page.getByLabel('action-link').getByText('Training')).toBeVisible({
                    timeout: TIMEOUTS.training,
                });
            });

            // Close the dialog
            await page.keyboard.press('Escape');
        });

        await test.step('run a test on imported dataset', async () => {
            // Verify that we have an active model
            const modelsPage = await projectPage.goToModelsPage();

            // Run test on ative model's FP16 version
            const activeModel = { name: 'MaskRCNN-EfficientNetB2B', version: '1' };
            const modelPage = await modelsPage.goToModel(activeModel.name, activeModel.version);
            const runTestDialogPage = await modelPage.openTestDialog(`${activeModel.name} OpenVINO FP16`);

            // Run and inspect tests
            const testName = `Test`;
            await runTestDialogPage.configureTest({ dataset: 'Testing set 1', testName });
            await runTestDialogPage.runTest();

            const testsPage = await modelsPage.seeTestProgress();

            await test.step('Wait for test to finish', async () => {
                await testsPage.waitForTestToFinish(testName);
            });

            const testPage = await testsPage.gotoTest(testName);
            const score = await testPage.getScore();

            // The model should be better than throwing coins
            expect(score).toBeGreaterThanOrEqual(25);
        });
    }
);

test(
    'Simple Card Detection',
    { tag: ['@daily'] },
    async ({ workspacesPage, page, mediaPage, projectPage, datasetPage, annotatorPage, segmentAnythingTool }) => {
        await page.goto('/');

        const uniqueSuffix = uuidv4();
        const projectName = `Card detection - [${uniqueSuffix}]`;

        const label = 'Card';

        await test.step('create project', async () => {
            const createProjectPage = await workspacesPage.createProject();

            const cardProjectPage = await createProjectPage.detection(projectName, [label]);

            await test.step('Verify project was created succesfully', async () => {
                await expectProjectToHaveType(cardProjectPage, 'Detection');
                await expectProjectToHaveLabels(cardProjectPage, [label]);
            });
        });

        const files: string[] = [];
        for (const suit of ['Hearts', 'Diamonds', 'Spades', 'Clubs']) {
            const path = resolveDatasetPath(`cards/${suit.toLocaleLowerCase()}`);
            files.push(...fs.readdirSync(path).map((filename) => resolveDatasetPath(path, filename)));
        }
        const totalFiles = files.length;

        await test.step('importing media', async () => {
            await projectPage.goToDatasetPage();

            const bucket = await mediaPage.getBucket();
            await bucket.uploadFiles(files);

            await expect(page.getByText(new RegExp(`Uploaded ${totalFiles} of ${totalFiles} files`))).toBeVisible({
                timeout: TIMEOUTS.uploadMedia,
            });

            await bucket.expectTotalMedia({ images: totalFiles });
        });

        const cardAnnotations = loadCardAnnotations();
        const AMOUNT_OF_ANNOTATIONS = 12; // totalFiles
        await test.step(`Annotate ${AMOUNT_OF_ANNOTATIONS} images`, async () => {
            await page.getByRole('button', { name: /annotate interactively/i }).click();

            await expect(page.getByRole('contentinfo')).toBeVisible();

            for (let idx = 0; idx < AMOUNT_OF_ANNOTATIONS; idx++) {
                // Select the segment anything tool everytime so that it waits for
                // "Extracting image features" to have finished before continueing
                await segmentAnythingTool.selectTool();

                const filename = await annotatorPage.selectedMediaFilename();
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
                await annotatorPage.submit();
                await expect(page).not.toHaveURL(url);
            }

            await annotatorPage.goBackToProjectPage();
        });

        await test.step('importing dataset', async () => {
            const datasetZipPath = resolveDatasetPath('cards/test-card-semantic-segmentation-dataset.zip');
            const datasetName = 'Testing set 1';

            // Create new testing set and open the import dataset dialog
            await datasetPage.createDataset();

            const importDatasetDialogPage = await datasetPage.selectDatasetTabMenuItem(
                datasetName,
                DatasetTabActions.ImportDataset
            );

            // Upload the dataset
            await importDatasetDialogPage.uploadDataset(datasetZipPath);

            const timeout = TIMEOUTS.importDataset;
            await page.getByRole('button', { name: /import/i }).click({ timeout });

            // Wait for the progress to start
            await expect(page.getByText(/Import dataset to project/)).toBeVisible({ timeout });
            await expect(page.getByText(/Waiting.../)).toBeVisible({ timeout });
        });

        await test.step('wait for import & training jobs to finish', async () => {
            // Open jobs dialog
            await page.getByLabel('Jobs in progress').click();

            // Select our project
            await page.getByLabel(/Job scheduler filter project/).fill(projectName);
            await page.getByRole('option', { name: projectName }).click();

            // Verify that the job is running
            await expect(page.getByLabel('action-link')).toHaveCount(2); // Training + import jobs

            await page.getByRole('tab', { name: 'Finished jobs' }).click();

            // Wait for the job to finish
            await test.step('import job', async () => {
                await expect(
                    page.getByLabel('action-link').getByText('Import Dataset to Existing Project')
                ).toBeVisible({
                    timeout: TIMEOUTS.importDataset,
                });
            });

            // Wait for training to finish
            await test.step('training job', async () => {
                await expect(page.getByLabel('action-link').getByText('Training')).toBeVisible({
                    timeout: TIMEOUTS.training,
                });
            });

            // Close the dialog
            await page.keyboard.press('Escape');
        });

        await test.step('run a test on imported dataset', async () => {
            // Verify that we have an active model
            const modelsPage = await projectPage.goToModelsPage();

            // Run test on ative model's FP16 version
            const activeModel = { name: 'MobileNetV2-ATSS', version: '1' };
            const modelPage = await modelsPage.goToModel(activeModel.name, activeModel.version);
            const runTestDialogPage = await modelPage.openTestDialog(`${activeModel.name} OpenVINO FP16`);

            // Run and inspect tests
            const testName = `Test`;
            await runTestDialogPage.configureTest({ dataset: 'Testing set 1', testName });
            await runTestDialogPage.runTest();

            const testsPage = await modelsPage.seeTestProgress();

            await test.step('Wait for test to finish', async () => {
                await testsPage.waitForTestToFinish(testName);
            });

            const testPage = await testsPage.gotoTest(testName);
            const score = await testPage.getScore();

            // The model should be better than throwing coins
            expect(score).toBeGreaterThanOrEqual(25);
        });
    }
);
