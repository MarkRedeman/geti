// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import { Button, Content, Heading } from '@geti/ui';

import { NotFound } from '../../../assets/images';
import { redirectTo } from '../../../shared/utils';

import classes from '../error-layout/error-layout.module.scss';

export const ResourceNotFound = (): JSX.Element => {
    return (
        <>
            <NotFound aria-label={'Not found'} />
            <Heading UNSAFE_className={classes.errorMessageHeader} data-testid={'resource-not-found-id'}>
                Resource not found
            </Heading>
            <Content UNSAFE_className={classes.errorMessage}>Please try refreshing the page</Content>
            <Button
                variant={'accent'}
                marginTop={'size-200'}
                onPress={() => {
                    // hard refresh
                    redirectTo(window.location.href);
                }}
            >
                Refresh
            </Button>
        </>
    );
};
