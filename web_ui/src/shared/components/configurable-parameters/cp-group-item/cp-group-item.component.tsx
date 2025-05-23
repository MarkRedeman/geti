// Copyright (C) 2022-2025 Intel Corporation
// LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE

import { useState } from 'react';

import { ActionButton, Flex, Text, View } from '@geti/ui';
import { ChevronRightSmallLight, ChevronUpLight } from '@geti/ui/icons';

import { idMatchingFormat } from '../../../../test-utils/id-utils';
import { ConfigParameterItemProp, ConfigurableParametersGroups } from '../configurable-parameters.interface';
import { CPParamsList } from '../cp-list/cp-list.component';

import classes from './cp-group-item.module.scss';

interface CPGroupItemProps extends ConfigParameterItemProp {
    group: ConfigurableParametersGroups;
    isExpandable: boolean;
}

export const CPGroupItem = ({ group, isExpandable, updateParameter }: CPGroupItemProps): JSX.Element => {
    const { header, parameters } = group;

    const [isExpanded, setIsExpanded] = useState<boolean>(false);

    return (
        <View marginBottom={'size-125'} marginEnd={'size-150'}>
            <Flex alignItems={'center'} justifyContent={'space-between'} marginBottom={'size-75'}>
                <Text id={`${idMatchingFormat(header)}-id`} UNSAFE_className={classes.configGroupHeaderTitle}>
                    {header}
                </Text>
                {isExpandable ? (
                    <ActionButton
                        id={`${idMatchingFormat(header)}-expand-button-id`}
                        isQuiet
                        onPress={() => setIsExpanded(!isExpanded)}
                        aria-label={'Show and hide group'}
                    >
                        {isExpanded ? (
                            <ChevronUpLight id={'chevron-up-id'} />
                        ) : (
                            <ChevronRightSmallLight id={'chevron-down-id'} />
                        )}
                    </ActionButton>
                ) : (
                    <></>
                )}
            </Flex>
            {isExpandable ? (
                isExpanded ? (
                    <CPParamsList parameters={parameters} updateParameter={updateParameter} header={header} />
                ) : (
                    <></>
                )
            ) : (
                <CPParamsList parameters={parameters} updateParameter={updateParameter} header={header} />
            )}
        </View>
    );
};
