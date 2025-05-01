// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE
import { TestType } from '@playwright/test';

import { JobType } from '../../../src/core/jobs/jobs.const';
import { JobsService } from '../../../src/core/jobs/services/jobs-service.interface';
import { MediaService } from '../../../src/core/media/services/media-service.interface';
import { ModelsService } from '../../../src/core/models/services/models.interface';
import { ProjectIdentifier } from '../../../src/core/projects/core.interface';
import { DatasetIdentifier } from '../../../src/core/projects/dataset.interface';
import { ProjectService, ProjectSortingOptions } from '../../../src/core/projects/services/project-service.interface';
import { TaskWithSupportedAlgorithms } from '../../../src/core/supported-algorithms/supported-algorithms.interface';
import { WorkspaceIdentifier } from '../../../src/core/workspaces/services/workspaces.interface';

type NextPage = null | string | undefined;
export async function* pagesIterator<T>(fetchPage: (nextPage: NextPage) => Promise<{ nextPage: NextPage; data: T }>) {
    let currentPage: NextPage = null;

    while (currentPage !== undefined) {
        const { data, nextPage } = await fetchPage(currentPage);

        currentPage = nextPage;
        yield data;
    }
}

export async function groupBy<T, K extends keyof any, M extends keyof any>(
    generator: AsyncGenerator<T>,
    keyFn: (item: T) => K,
    mapFn: (item: T) => M
): Promise<Record<K, M[]>> {
    const groups: Record<K, M[]> = {} as Record<K, M[]>;

    for await (const item of generator) {
        const key = keyFn(item);
        if (!groups[key]) {
            groups[key] = [];
        }
        groups[key].push(mapFn(item));
    }

    return groups;
}

export async function* flatten<T>(generator: AsyncGenerator<T[]>) {
    for await (const items of generator) {
        for (const item of items) {
            yield item;
        }
    }
}

export async function* filter<T>(generator: AsyncGenerator<T>, fn: (item: T) => boolean) {
    for await (const item of generator) {
        if (fn(item)) {
            yield item;
        }
    }
}

export async function* map<T, FT>(generator: AsyncGenerator<T>, fn: (item: T) => FT) {
    for await (const item of generator) {
        yield fn(item);
    }
}

export async function collect<T>(generator: AsyncGenerator<T>) {
    const items: Array<Awaited<T>> = [];
    for await (const item of generator) {
        items.push(item);
    }
    return items;
}

export function mediaPagesIterator(datasetIdentifier: DatasetIdentifier, mediaService: MediaService, perPage: number) {
    const mediaItemsPages = pagesIterator(async (currentPage) => {
        const { media: data, nextPage } = await mediaService.getAdvancedFilterMedia(
            datasetIdentifier,
            perPage,
            currentPage,
            {},
            {}
        );

        return { data, nextPage };
    });

    return flatten(mediaItemsPages);
}
const cardProjects = [
    '67b88889c3d4b31dec9ab03e',
    '67b88923c3d4b31dec9ab1ca',
    '67b88a9ec3d4b31dec9ab271',
    '67b88c37c3d4b31dec9ab317',
    '67b88d86c3d4b31dec9ab3bd',
    '67b88e8fc3d4b31dec9ab463',
];

export const projectsPagesIterator = (workspaceIdentifier: WorkspaceIdentifier, projectService: ProjectService) => {
    return filter(
        flatten(
            pagesIterator(async (currentPage) => {
                const { projects: data, nextPage } = await projectService.getProjects(
                    workspaceIdentifier,
                    { sortBy: ProjectSortingOptions.creationDate, sortDir: 'dsc' },
                    currentPage
                );

                return { data, nextPage };
            })
        ),
        (project) => true //cardProjects.includes(project.id)
    );
};

export function modelGroupsIterator(
    projectIdentifier: ProjectIdentifier,
    modelsService: ModelsService,
    taskWithSupportedAlgorithms: TaskWithSupportedAlgorithms
) {
    const mediaItemsPages = pagesIterator(async () => {
        const data = await modelsService.getModels(projectIdentifier, taskWithSupportedAlgorithms);

        return { data, nextPage: null };
    });

    return flatten(mediaItemsPages);
}

export function jobsIterator(
    workspaceIdentifier: WorkspaceIdentifier,
    jobsService: JobsService,
    projectIdentifier: ProjectIdentifier | undefined,
    jobTypes: Array<JobType>
) {
    const mediaItemsPages = pagesIterator(async (currentPage) => {
        const { jobs, nextPage } = await jobsService.getJobs(
            workspaceIdentifier,
            {
                projectId: projectIdentifier?.projectId,
                jobTypes,
                limit: 100,
            },
            currentPage ?? undefined
        );

        console.log(jobs.length);
        //console.log({jobs, nextPage,});

        return { data: jobs, nextPage };
    });

    return flatten(mediaItemsPages);
}

export async function* mediaItemsIterator(datasetIdentifier: DatasetIdentifier, mediaService: MediaService) {
    const mediaItems = mediaPagesIterator(datasetIdentifier, mediaService, 50);

    for await (const mediaItem of mediaItems) {
        yield mediaItem;
    }
}

export async function* stepIterator<T>(test: TestType, iterator: AsyncIterator<T>) {
    for await (const item of iterator) {
        await test.step('', async () => {});
    }
}
