// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import fs from 'fs';

import { v4 as uuidv4 } from 'uuid';

import { DatasetTabActions } from '../../../src/pages/project-details/components/project-dataset/utils';
import { resolveDatasetPath } from '../../utils/dataset';
import { expectProjectToHaveLabels, expectProjectToHaveType } from './../../features/project-creation/expect';
import { expect } from './../../fixtures/base-test';
import { test } from './../fixtures';
import { TIMEOUTS } from './timeouts';

test(
    'Simple Card anomaly detection',
    { tag: ['@daily'] },
    async ({ workspacesPage, page, projectPage, datasetPage, anomalyMediaPage }) => {
        await page.goto('/');

        const uniqueSuffix = uuidv4();
        const projectName = `Card anomaly detection - [${uniqueSuffix}]`;

        await test.step('create project', async () => {
            const createProjectPage = await workspacesPage.createProject();

            const cardProjectPage = await createProjectPage.anomalyDetection(projectName);

            await test.step('Verify project was created succesfully', async () => {
                await expectProjectToHaveType(cardProjectPage, 'Anomaly detection');
                await expectProjectToHaveLabels(cardProjectPage, ['Normal', 'Anomalous']);
            });
        });

        await test.step('importing media', async () => {
            await projectPage.goToDatasetPage();

            const normalBucket = await anomalyMediaPage.getNormalBucket();
            const anomalousBucket = await anomalyMediaPage.getAnomalousBucket();

            let totalFiles = 0;
            for (const suit of ['Spades', 'Clubs']) {
                await test.step(`Uploading "${suit}"`, async () => {
                    const path = resolveDatasetPath(`cards/${suit.toLocaleLowerCase()}`);

                    // Take 12 images per suit so that we train with minimal images
                    const files = fs.readdirSync(path).map((filename) => resolveDatasetPath(path, filename));

                    await normalBucket.uploadFiles(files);

                    totalFiles += files.length;

                    await expect(async () => {
                        const message = page.getByText(new RegExp(`Uploaded ${totalFiles} of ${totalFiles} files`));
                        await expect(message).toBeVisible();
                    }).toPass({
                        timeout: TIMEOUTS.uploadMedia,
                    });

                    await normalBucket.expectTotalMedia({ images: totalFiles });
                });
            }

            for (const suit of ['Hearts']) {
                await test.step(`Uploading "${suit}"`, async () => {
                    const path = resolveDatasetPath(`cards/${suit.toLocaleLowerCase()}`);

                    // Take 12 images per suit so that we train with minimal images
                    const files = fs.readdirSync(path).map((filename) => resolveDatasetPath(path, filename));

                    await anomalousBucket.uploadFiles(files);

                    totalFiles += files.length;

                    await expect(async () => {
                        const message = page.getByText(new RegExp(`Uploaded ${totalFiles} of ${totalFiles} files`));
                        await expect(message).toBeVisible();
                    }).toPass({
                        timeout: TIMEOUTS.uploadMedia,
                    });

                    await anomalousBucket.expectTotalMedia({ images: files.length });
                });
            }
        });

        await test.step('start training', async () => {
            await anomalyMediaPage.startTrainingFromNotification();
        });

        await test.step('importing dataset', async () => {
            const datasetZipPath = resolveDatasetPath('cards/test-card-anomaly-dataset.zip');
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
            await expect(page.getByText('Label mapping')).toBeVisible({ timeout });

            await importDatasetDialogPage.assignLabels();

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
            const activeModel = { name: 'PADIM', version: '1' };
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
