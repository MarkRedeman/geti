// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import { JobState, JobType } from '../../../src/core/jobs/jobs.const';
import { JobsService } from '../../../src/core/jobs/services/jobs-service.interface';
import { ProjectIdentifier } from '../../../src/core/projects/core.interface';
import { delay } from '../../../src/shared/utils';

export const waitForJobToFinish = async (
    jobsService: JobsService,
    projectIdentifier: ProjectIdentifier,
    jobTypes: Array<JobType>
) => {
    console.log('Start fetching jobs');

    let isModelTesting = true;

    while (isModelTesting) {
        const { jobs, jobsCount } = await jobsService.getJobs(
            projectIdentifier,
            {
                projectId: projectIdentifier.projectId,
                jobTypes,
                limit: 100,
                // TODO: make it a running thing, then use jobsCount instead and set limit to 1
                // jobState: JobState.RUNNING
            },
            undefined
        );

        const activeJobs = jobs.filter((job) => [JobState.RUNNING, JobState.SCHEDULED].includes(job.state));

        isModelTesting = activeJobs.length > 0;
        if (isModelTesting === false) {
            break;
        }

        const now = new Date();
        console.log(`${now.toISOString()} - Waiting for jobs to finish... (${activeJobs.length} / ${jobs.length})`);

        await delay(30_000);
    }

    console.log('All jobs have finished');
};
