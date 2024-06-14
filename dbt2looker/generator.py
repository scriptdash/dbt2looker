import logging
import os
import re

import lkml

from . import models

LOOKER_DTYPE_MAP = {
    'bigquery': {
        'INT64':     'number',
        'INTEGER':   'number',
        'FLOAT':     'number',
        'FLOAT64':   'number',
        'NUMERIC':   'number',
        'BIGNUMERIC': 'number',
        'BOOLEAN':   'yesno',
        'STRING':    'string',
        'TIMESTAMP': 'timestamp',
        'DATETIME':  'datetime',
        'DATE':      'date',
        'TIME':      'string',    # Can time-only be handled better in looker?
        'BOOL':      'yesno',
        'ARRAY':     'string',
        'GEOGRAPHY': 'string',
        'BYTES': 'string',
    },
    'snowflake': {
        'NUMBER': 'number',
        'DECIMAL': 'number',
        'NUMERIC': 'number',
        'INT': 'number',
        'INTEGER': 'number',
        'BIGINT': 'number',
        'SMALLINT': 'number',
        'FLOAT': 'number',
        'FLOAT4': 'number',
        'FLOAT8': 'number',
        'DOUBLE': 'number',
        'DOUBLE PRECISION': 'number',
        'REAL': 'number',
        'VARCHAR': 'string',
        'CHAR': 'string',
        'CHARACTER': 'string',
        'STRING': 'string',
        'TEXT': 'string',
        'BINARY': 'string',
        'VARBINARY': 'string',
        'BOOLEAN': 'yesno',
        'DATE': 'date',
        'DATETIME': 'datetime',
        'TIME': 'string',        # can we support time?
        'TIMESTAMP': 'timestamp',
        'TIMESTAMP_NTZ': 'timestamp',
        'TIMESTAMP_LTZ': 'timestamp', # not supported (see https://docs.looker.com/reference/field-params/dimension_group) but we can cast
        'TIMESTAMP_TZ': 'timestamp', # not supported (see https://docs.looker.com/reference/field-params/dimension_group) but we can cast
        'VARIANT': 'string',
        'OBJECT': 'string',
        'ARRAY': 'string',
        'GEOGRAPHY': 'string',
    },
    'redshift': {
        'SMALLINT': 'number',
        'INT2': 'number',
        'INTEGER': 'number',
        'INT': 'number',
        'INT4': 'number',
        'BIGINT': 'number',
        'INT8': 'number',
        'DECIMAL': 'number',
        'NUMERIC': 'number',
        'REAL': 'number',
        'FLOAT4': 'number',
        'DOUBLE PRECISION': 'number',
        'FLOAT8': 'number',
        'FLOAT': 'number',
        'BOOLEAN': 'yesno',
        'BOOL': 'yesno',
        'CHAR': 'string',
        'CHARACTER': 'string',
        'NCHAR': 'string',
        'BPCHAR': 'string',
        'VARCHAR': 'string',
        'CHARACTER VARYING': 'string',
        'NVARCHAR': 'string',
        'TEXT': 'string',
        'DATE': 'date',
        'TIMESTAMP': 'timestamp',
        'TIMESTAMP WITHOUT TIME ZONE': 'timestamp',
        # TIMESTAMPTZ not supported
        # TIMESTAMP WITH TIME ZONE not supported
        'GEOMETRY': 'string',
        # HLLSKETCH not supported
        'TIME': 'string',
        'TIME WITHOUT TIME ZONE': 'string',
        # TIMETZ not supported
        # TIME WITH TIME ZONE not supported
    },
    'postgres': {
        # BIT, BIT VARYING, VARBIT not supported
        # BOX not supported
        # BYTEA not supported
        # CIRCLE not supported
        # INTERVAL not supported
        # LINE not supported
        # LSEG not supported
        # PATH not supported
        # POINT not supported
        # POLYGON not supported
        # TSQUERY, TSVECTOR not supported
        'XML': 'string',
        'UUID': 'string',
        'PG_LSN': 'string',
        'MACADDR': 'string',
        'JSON': 'string',
        'JSONB': 'string',
        'CIDR': 'string',
        'INET': 'string',
        'MONEY': 'number',
        'SMALLINT': 'number',
        'INT2': 'number',
        'SMALLSERIAL': 'number',
        'SERIAL2': 'number',
        'INTEGER': 'number',
        'INT': 'number',
        'INT4': 'number',
        'SERIAL': 'number',
        'SERIAL4': 'number',
        'BIGINT': 'number',
        'INT8': 'number',
        'BIGSERIAL': 'number',
        'SERIAL8': 'number',
        'DECIMAL': 'number',
        'NUMERIC': 'number',
        'REAL': 'number',
        'FLOAT4': 'number',
        'DOUBLE PRECISION': 'number',
        'FLOAT8': 'number',
        'FLOAT': 'number',
        'BOOLEAN': 'yesno',
        'BOOL': 'yesno',
        'CHAR': 'string',
        'CHARACTER': 'string',
        'NCHAR': 'string',
        'BPCHAR': 'string',
        'VARCHAR': 'string',
        'CHARACTER VARYING': 'string',
        'NVARCHAR': 'string',
        'TEXT': 'string',
        'DATE': 'date',
        'TIMESTAMP': 'timestamp',
        'TIMESTAMP WITHOUT TIME ZONE': 'timestamp',
        # TIMESTAMPTZ not supported
        # TIMESTAMP WITH TIME ZONE not supported
        'GEOMETRY': 'string',
        # HLLSKETCH not supported
        'TIME': 'string',
        'TIME WITHOUT TIME ZONE': 'string',
        'STRING': 'string',
        # TIMETZ not supported
        # TIME WITH TIME ZONE not supported
    },
    'spark': {
        'BYTE':        'number',
        'SHORT':       'number',
        'INTEGER':     'number',
        'LONG':        'number',
        'FLOAT':       'number',
        'DOUBLE':      'number',
        'DECIMAL':     'number',
        'STRING':      'string',
        'VARCHAR':     'string',
        'CHAR':        'string',
        'BOOLEAN':     'yesno',
        'TIMESTAMP':   'timestamp',
        'DATE':        'datetime',
    }
}

looker_date_time_types = ['datetime', 'timestamp']
looker_date_types = ['date']
looker_scalar_types = ['number', 'yesno', 'string']

looker_timeframes = [
    'raw',
    'time',
    'date',
    'week',
    'month',
    'quarter',
    'year',
]


def normalise_spark_types(column_type: str) -> str:
    return re.match(r'^[^\(]*', column_type).group(0)


def map_adapter_type_to_looker(adapter_type: models.SupportedDbtAdapters, column_type: str):
    if not column_type:
        return None
    normalised_column_type = (normalise_spark_types(column_type) if adapter_type == models.SupportedDbtAdapters.spark.value else column_type).upper()
    looker_type = LOOKER_DTYPE_MAP[adapter_type].get(normalised_column_type)
    if (column_type is not None) and (looker_type is None):
        logging.warning(f'Column type {column_type} not supported for conversion from {adapter_type} to looker. No dimension will be created.')
    return looker_type


def lookml_date_time_dimension_group(column: models.DbtModelColumn, adapter_type: models.SupportedDbtAdapters):
    datatype = map_adapter_type_to_looker(adapter_type, column.data_type)
    if adapter_type == models.SupportedDbtAdapters.snowflake.value and column.data_type in ("TIMESTAMP_LTZ", "TIMESTAMP_TZ"):
        logging.debug(f"Snowflake TIMESTAMP_LTZ and TIMESTAMP_TZ are not supported by Looker. Casting to TIMESTAMP_NTZ")
        default_sql = f'CAST(${{TABLE}}.{column.name}) AS TIMESTAMP_NTZ'
    else:
        default_sql = f'${{TABLE}}.{column.name}'
    return {
        'name': column.meta.dimension.name or column.name,
        'type': 'time',
        'sql': column.meta.dimension.sql or default_sql,
        'description': column.meta.dimension.description or column.description,
        'datatype': datatype,
        'timeframes': ['raw', 'time', 'hour', 'date', 'week', 'month', 'quarter', 'year']
    }


def lookml_date_dimension_group(column: models.DbtModelColumn, adapter_type: models.SupportedDbtAdapters):
    return {
        'name': column.meta.dimension.name or column.name,
        'type': 'time',
        'sql': column.meta.dimension.sql or f'${{TABLE}}.{column.name}',
        'description': column.meta.dimension.description or column.description,
        'datatype': map_adapter_type_to_looker(adapter_type, column.data_type),
        'timeframes': ['raw', 'date', 'week', 'month', 'quarter', 'year']
    }


def lookml_dimension_groups_from_model(model: models.DbtModel, adapter_type: models.SupportedDbtAdapters):
    date_times = [
        lookml_date_time_dimension_group(column, adapter_type)
        for column in model.columns.values()
        if map_adapter_type_to_looker(adapter_type, column.data_type) in looker_date_time_types
    ]
    dates = [
        lookml_date_dimension_group(column, adapter_type)
        for column in model.columns.values()
        if column.meta.dimension.enabled
        and map_adapter_type_to_looker(adapter_type, column.data_type) in looker_date_types
    ]
    return date_times + dates


def lookml_dimensions_from_model(model: models.DbtModel, adapter_type: models.SupportedDbtAdapters):
    dimensions = []
    for column in model.columns.values():
        if not column.meta.dimension.enabled:
            logging.debug(f'Dimension {column.name} is disabled in model {model.name}')
            continue
        if map_adapter_type_to_looker(adapter_type, column.data_type) not in looker_scalar_types:
            logging.debug(f'Column {column.name} is not a scalar type, no dimension will be created.')
            continue
        lookml_dict = {
            'name': column.meta.dimension.name or column.name,
            'type': map_adapter_type_to_looker(adapter_type, column.data_type),
            'sql': column.meta.dimension.sql or f'${{TABLE}}.{column.name}',
            'description': column.meta.dimension.description or column.description,
        }
        if (column.meta.dimension.value_format_name
                and map_adapter_type_to_looker(adapter_type, column.data_type) == 'number'):
            lookml_dict['value_format_name'] =  column.meta.dimension.value_format_name.value
        if column.constraints and "primary_key" in [constraint.type for constraint in column.constraints]:
            lookml_dict['primary_key'] = "yes"
        if column.meta.dimension.hidden:
            lookml_dict['hidden'] = 'yes'
        dimensions.append(lookml_dict)

    return dimensions


def lookml_measure_filters(measure: models.Dbt2LookerMeasure, model: models.DbtModel):
    try:
        columns = {
            column_name: model.columns[column_name]
            for f in measure.filters
            for column_name in f
        }
    except KeyError as e:
        raise ValueError(
            f'Model {model.unique_id} contains a measure that references a non_existent column: {e}\n'
            f'Ensure that dbt model {model.unique_id} contains a column: {e}'
        ) from e
    return [{
        (columns[column_name].meta.dimension.name or column_name): fexpr
        for column_name, fexpr in f.items()
    } for f in measure.filters]


def lookml_measures_from_model(model: models.DbtModel):
    return [
        lookml_measure(measure_name, column, measure, model)
        for column in model.columns.values()
        for measure_name, measure in {
            **column.meta.measures, **column.meta.measure, **column.meta.metrics, **column.meta.metric
        }.items()
    ]


def lookml_measure(measure_name: str, column: models.DbtModelColumn, measure: models.Dbt2LookerMeasure, model: models.DbtModel):
    m = {
        'name': measure_name,
        'type': measure.type.value,
        'sql': measure.sql or f'${{TABLE}}.{column.name}',
        'description': measure.description or column.description or f'{measure.type.value.capitalize()} of {column.name}',
    }
    if measure.filters:
        m['filters'] = lookml_measure_filters(measure, model)
    if measure.value_format_name:
        m['value_format_name'] = measure.value_format_name.value
    if measure.group_label:
        m['group_label'] = measure.group_label
    if measure.label:
        m['label'] = measure.label
    if measure.hidden:
        m['hidden'] = measure.hidden.value
    if measure.drill_fields:
        m['drill_fields'] = measure.drill_fields
    return m


def lookml_view_from_dbt_model(model: models.DbtModel, adapter_type: models.SupportedDbtAdapters, use_file_path: bool):
    lookml = {
        'view': {
            'name': model.name,
            'sql_table_name': model.relation_name,
            'dimension_groups': lookml_dimension_groups_from_model(model, adapter_type),
            'dimensions': lookml_dimensions_from_model(model, adapter_type),
            'measures': lookml_measures_from_model(model),
        }
    }
    logging.debug(
        f'Created view from model %s with %d measures, %d dimensions',
        model.name,
        len(lookml['view']['measures']),
        len(lookml['view']['dimensions']),
    )
    contents = lkml.dump(lookml)
    filename = f'{model.name}.view.lkml'
    return models.LookViewFile(filename=filename,
                               directory=os.path.dirname(model.path) if use_file_path else '',
                               contents=contents)


def lookml_model_from_dbt_model(model: models.DbtModel, connection_name: str, use_file_path: bool):
    # Note: assumes view names = model names
    #       and models are unique across dbt packages in project
    lookml = {
        'connection': connection_name,
        'include': '/views/*',
        'explore': {
            'name': model.name,
            'description': model.description,
            'joins': [
                {
                    'name': join.join,
                    'type': join.type.value,
                    'relationship': join.relationship.value,
                    'sql_on': join.sql_on,
                    'view_label': join.view_label or join.join,
                }
                for join in model.meta.joins
            ]
        }
    }
    contents = lkml.dump(lookml)
    filename = f'{model.name}.model.lkml'
    return models.LookModelFile(
        filename=filename,
        directory=os.path.dirname(model.path) if use_file_path else '',
        contents=contents,
    )
