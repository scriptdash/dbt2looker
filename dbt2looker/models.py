from enum import Enum
from pathlib import Path
from typing import Any, Union, Dict, List, Optional

from pydantic_core import PydanticCustomError
try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal
from pydantic import BaseModel, Field, field_validator


class SupportedDbtAdapters(str, Enum):
    bigquery = 'bigquery'
    postgres = 'postgres'
    redshift = 'redshift'
    snowflake = 'snowflake'
    spark = 'spark'


# Lookml types
class LookerMeasureType(str, Enum):
    number = 'number'
    string = 'string'
    average = 'average'
    average_distinct = 'average_distinct'
    count = 'count'
    count_distinct = 'count_distinct'
    list = 'list'
    max = 'max'
    median = 'median'
    median_distinct = 'median_distinct'
    min = 'min'
    # percentile = 'percentile'
    # percentile_distinct = 'percentile_distinct'
    sum = 'sum'
    sum_distinct = 'sum_distinct'


class LookerJoinType(str, Enum):
    left_outer = 'left_outer'
    full_outer = 'full_outer'
    inner = 'inner'
    cross = 'cross'


class LookerJoinRelationship(str, Enum):
    many_to_one = 'many_to_one'
    many_to_many = 'many_to_many'
    one_to_many = 'one_to_many'
    one_to_one = 'one_to_one'


class LookerValueFormatName(str, Enum):
    decimal_0 = 'decimal_0'
    decimal_1 = 'decimal_1'
    decimal_2 = 'decimal_2'
    decimal_3 = 'decimal_3'
    decimal_4 = 'decimal_4'
    usd_0 = 'usd_0'
    usd = 'usd'
    gbp_0 = 'gbp_0'
    gbp = 'gbp'
    eur_0 = 'eur_0'
    eur = 'eur'
    id = 'id'
    percent_0 = 'percent_0'
    percent_1 = 'percent_1'
    percent_2 = 'percent_2'
    percent_3 = 'percent_3'
    percent_4 = 'percent_4'


class LookerHiddenType(str, Enum):
    yes = 'yes'
    no = 'no'


class Dbt2LookerMeasure(BaseModel):
    type: LookerMeasureType
    filters: Optional[List[Dict[str, str]]] = []
    description: Optional[str] = None
    sql: Optional[str] = None
    value_format_name: Optional[LookerValueFormatName]
    group_label: Optional[str] = None
    label: Optional[str] = None
    hidden: Optional[LookerHiddenType] = None
    drill_fields: Optional[List[str]] = None

    @field_validator('filters')
    def filters_are_singular_dicts(cls, v: List[Dict[str, str]]):
        if v is not None:
            for f in v:
                if len(f) != 1:
                    raise ValueError('Multiple filter names provided for a single filter in measure block')
        return v


class Dbt2LookerDimension(BaseModel):
    enabled: Optional[bool] = True
    name: Optional[str] = None
    sql: Optional[str] = None
    description: Optional[str] = None
    value_format_name: Optional[LookerValueFormatName] = None
    hidden: bool = False


class Dbt2LookerMeta(BaseModel):
    measures: Optional[Dict[str, Dbt2LookerMeasure]] = {}
    measure: Optional[Dict[str, Dbt2LookerMeasure]] = {}
    metrics: Optional[Dict[str, Dbt2LookerMeasure]] = {}
    metric: Optional[Dict[str, Dbt2LookerMeasure]] = {}
    dimension: Optional[Dbt2LookerDimension] = Dbt2LookerDimension()


# Looker file types
class LookViewFile(BaseModel):
    filename: str
    directory: str
    contents: str


class LookModelFile(BaseModel):
    filename: str
    directory: str
    contents: str


# dbt config types
class DbtProjectConfig(BaseModel):
    name: str

class ConstraintType(str, Enum):
    not_null = 'not_null'
    primary_key = 'primary_key'
    foreign_key = 'foreign_key'
    unique = 'unique'
    check = 'check'

class DbtColumnConstraint(BaseModel):
    type: ConstraintType
    name: Optional[str] = None
    expression: Optional[str] = None

class DbtModelColumnMeta(Dbt2LookerMeta):
    pass

class DbtModelColumn(BaseModel):
    name: str
    description: str
    data_type: Optional[str] = None
    constraints: Optional[List[DbtColumnConstraint]] = None
    meta: DbtModelColumnMeta


class DbtNode(BaseModel):
    unique_id: str
    resource_type: str
    config: Dict[str, Any]


class Dbt2LookerExploreJoin(BaseModel):
    join: str
    type: Optional[LookerJoinType] = LookerJoinType.left_outer
    relationship: Optional[LookerJoinRelationship] = LookerJoinRelationship.many_to_one
    sql_on: str
    view_label: Optional[str] = None

class Dbt2LookerModelMeta(BaseModel):
    joins: Optional[List[Dbt2LookerExploreJoin]] = []


class DbtModelMeta(Dbt2LookerModelMeta):
    pass


class DbtModel(DbtNode):
    resource_type: Literal['model']
    relation_name: str
    db_schema: str = Field(..., alias='schema')
    name: str
    description: str
    columns: Dict[str, DbtModelColumn]
    tags: List[str]
    meta: DbtModelMeta
    path: Path

    @field_validator('columns')
    def case_insensitive_column_names(cls, v: Dict[str, DbtModelColumn]):
        return {
            name.lower(): column.copy(update={'name': column.name.lower()})
            for name, column in v.items()
        }


class DbtManifestMetadata(BaseModel):
    adapter_type: str

    @field_validator('adapter_type')
    def adapter_must_be_supported(cls, v):
        try:
            SupportedDbtAdapters(v)
        except ValueError:
            raise PydanticCustomError(
                'unsupported_dbt_adapter',
                '{wrong_value} is not a supported dbt adapter',
                dict(wrong_value=v)
            )
        return v


class DbtManifest(BaseModel):
    nodes: Dict[str, Union[DbtModel, DbtNode]]
    metadata: DbtManifestMetadata


class DbtCatalogNodeMetadata(BaseModel):
    type: str
    db_schema: str = Field(..., alias='schema')
    name: str
    comment: Optional[str] = None
    owner: Optional[str] = None


class DbtCatalogNodeColumn(BaseModel):
    type: str
    comment: Optional[str] = None
    index: int
    name: str


class DbtCatalogNode(BaseModel):
    metadata: DbtCatalogNodeMetadata
    columns: Dict[str, DbtCatalogNodeColumn]

    @field_validator('columns')
    def case_insensitive_column_names(cls, v: Dict[str, DbtCatalogNodeColumn]):
        return {
            name.lower(): column.copy(update={'name': column.name.lower()})
            for name, column in v.items()
        }


class DbtCatalog(BaseModel):
    nodes: Dict[str, DbtCatalogNode]
