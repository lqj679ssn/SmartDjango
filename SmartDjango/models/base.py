import datetime
from typing import List, Tuple

from django.db import models

from SmartDjango import Packing, BaseError
from . import Manager, fields


class Constraint:
    LENGTH_T = '{0}({1})的长度不应%s{2}'
    VALUE_T = '{0}({1})不应%s{2}'

    def __init__(self, field, type_, boundary=True, compare=None, template=None):
        self.field, self.type, self.boundary = field, type_, boundary
        self.compare = compare or (lambda x: x)
        self.error_template = template or self.VALUE_T

    @Packing.pack
    def fit(self, field, value):
        if isinstance(field, fields.CharField):
            max_, min_ = field.max_length, field.min_length
        else:
            max_, min_ = field.max_value, field.min_value
        if max_ and max_ < self.compare(value):
            return BaseError.FIELD_FORMAT((self.error_template % '大于').format(
                field.name, field.verbose_name, max_
            ))
        if min_ and min_ > self.compare(value):
            return BaseError.FIELD_FORMAT((self.error_template % '小雨').format(
                field.name, field.verbose_name, min_
            ))


CONSTRAINTS = [
    Constraint(fields.CharField, str),
    Constraint(fields.IntegerField, int),
    Constraint(fields.FloatField, float),
    Constraint(fields.BooleanField, bool, boundary=False),
    Constraint(fields.DateField, datetime.date),
    Constraint(fields.DateTimeField, datetime.datetime),
]


class Model(models.Model):
    objects = Manager()

    class Meta:
        abstract = True
        default_manager_name = 'objects'

    @classmethod
    def get_fields(cls, field_names: List[str]) -> Tuple[models.Field]:
        field_jar = dict()
        for field in cls._meta.fields:
            field_jar[field.name] = field

        field_list = []  # type: List[models.Field]
        for field_name in field_names:
            field_list.append(field_jar.get(field_name))

        return tuple(field_list)

    @classmethod
    def get_field(cls, field_name) -> models.Field:
        return cls.get_fields([field_name])[0]

    @classmethod
    def get_params(cls, field_names):
        from ..p import P
        return P.from_fields(cls.get_fields(field_names))

    @classmethod
    def get_param(cls, field_name):
        from ..p import P
        return P.from_field(cls.get_field(field_name))

    P = get_params

    @staticmethod
    def field_validator(field: models.Field):
        attr = field.name
        verbose = field.verbose_name
        cls = field.model

        @Packing.pack
        def validate(value):
            for constraint in CONSTRAINTS:
                if isinstance(field, constraint.field):
                    if not isinstance(value, constraint.type):
                        return BaseError.FIELD_FORMAT('%s(%s)类型错误' % (attr, verbose))
                    if constraint.boundary:
                        constraint.fit(field, value)
                    break

            if field.choices:
                choice_match = False
                for choice in field.choices:
                    if value == choice[0]:
                        choice_match = True
                        break
                if not choice_match:
                    return BaseError.FIELD_FORMAT('%s(%s)不在可选择范围之内' % (attr, verbose))

            custom_validator = getattr(cls, '_valid_%s' % attr)
            if callable(custom_validator):
                try:
                    custom_validator(value)
                except Packing as ret:
                    return ret
                except Exception:
                    return BaseError.FIELD_VALIDATOR('%s(%s)校验函数崩溃' % (attr, verbose))

            return validate
