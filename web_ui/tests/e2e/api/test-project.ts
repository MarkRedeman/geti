// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import { JobState, JobType } from '../../../src/core/jobs/jobs.const';
import { createApiJobsService } from '../../../src/core/jobs/services/api-jobs-service';
import { createApiWorkspacesService } from '../../../src/core/workspaces/services/api-workspaces-service';
import { delay } from '../../../src/shared/utils';
import { ServiceConfiguration } from '../api-fixtures';

export class TestProject {
    private organizationId?: string;
    private workspaceId?: string;
    public projectId?: string;

    constructor(private apiServiceConfiguration: ServiceConfiguration) {}

    async getWorkspace(workspaceIndex: number = 0) {
        const workspaceService = createApiWorkspacesService(this.apiServiceConfiguration);

        const organization = await this.apiServiceConfiguration.instance.get<{ organizationId: string }>(
            this.apiServiceConfiguration.router.PREFIX(`/api/v1/personal_access_tokens/organization`)
        );

        const organizationId = organization.data.organizationId;
        this.organizationId = organizationId;

        const workspaces = await workspaceService.getWorkspaces(organizationId);
        const workspaceId = workspaces.at(workspaceIndex)?.id;

        if (workspaceId === undefined) {
            throw new Error('Organization has no workspaces');
        }

        this.workspaceId = workspaceId;
    }

    /**
     * Wait until the the current project no longer has any active jobs of the
     * provided job types
     **/
    async waitForNoActiveJobs(jobTypes: Array<JobType>) {
        const projectIdentifier = this.projectIdentifier();
        const jobsService = createApiJobsService(this.apiServiceConfiguration);
        console.log('Start fetching jobs');

        const isModelTesting = true;

        while (isModelTesting) {
            const { jobs, jobsCount } = await jobsService.getJobs(
                projectIdentifier,
                {
                    projectId: projectIdentifier.projectId,
                    jobTypes,
                    limit: 100,
                },
                undefined
            );

            // Stop waiting if there are no more acctive jobs
            const activeJobs = jobs.filter((job) => [JobState.RUNNING, JobState.SCHEDULED].includes(job.state));
            if (activeJobs.length === 0) {
                break;
            }

            const now = new Date();
            console.log(`${now.toISOString()} - Waiting for jobs to finish... (${activeJobs.length} / ${jobs.length})`);
            console.log({ jobs, jobsCount });

            await delay(30_000);
        }

        console.log('All jobs have finished');
    }

    organizationIdentifier() {
        if (this.organizationId === undefined) {
            throw new Error('Organization not initialized');
        }

        return {
            organizationId: this.organizationId,
        };
    }

    workspaceIdentifier() {
        if (this.workspaceId === undefined) {
            throw new Error('Workspace not initialized');
        }

        return {
            ...this.organizationIdentifier(),
            workspaceId: this.workspaceId,
        };
    }

    projectIdentifier() {
        if (this.projectId === undefined) {
            throw new Error('Project not initialized');
        }

        return {
            ...this.workspaceIdentifier(),
            projectId: this.projectId,
        };
    }
}
