
import logging

from django.db import connections
from django.db.models.fields.related_descriptors import (ForwardManyToOneDescriptor, ForwardOneToOneDescriptor,
                                                         ReverseOneToOneDescriptor)

from traceback import extract_stack


class NPlusOne:
    """
    Class decorator to wrap around Django's related field descriptors' __get__ method

    Django uses forward/reverse descriptors for a field to get related models from cache, if present, or make a database
    query for current model record. This class wraps the descriptors __get__ method with a decorator to find out if a
    database query was made or not. If Django made a database query this will probably lead to N+1 queries so decorator
    will detect that and print a debug message to alert developer.
    """

    def __init__(self, get_method):
        self.get_method = get_method

    def total_queries(self):
        """
        Get number of database queries on current connections
        """
        db_connections = [connections[db_alias] for db_alias in connections.databases]
        return sum(len(db_connection.queries) for db_connection in db_connections)

    def get_field_name(self, descriptor_instance):
        """
        Get the name of related field based on the kind of descriptor we are dealing with

        :param descriptor_instance: type of descriptor representing the django model relationship
        :return: the string name of the related field or None if unsupported descriptor
        """
        forward_descriptors = [ForwardManyToOneDescriptor, ForwardOneToOneDescriptor]
        if any(isinstance(descriptor_instance, descriptor_class) for descriptor_class in forward_descriptors):
            return descriptor_instance.field.name

        reverse_descriptors = [ReverseOneToOneDescriptor]
        if any(isinstance(descriptor_instance, descriptor_class) for descriptor_class in reverse_descriptors):
            return descriptor_instance.related.name

        # since this message is meant to be used as advisor, we can't throw exception
        return None

    def __call__(self, *args, **kwargs):
        """
        Get query count before and after callng get_method, if it increases, N+1 is found

        :param args: the positional arguments passed to get_method
        :param kwargs: the keyword arguments passed to get_method
        """

        # we expect two arguments to get_method of descriptor i.e. self and the field's model instance
        if len(args) < 2:
            return self.get_method(*args, **kwargs)

        descriptor_instance = args[0]
        model = args[1]

        pre_num_queries = self.total_queries()
        related_model = self.get_method(*args, **kwargs)
        post_num_queries = self.total_queries()

        # see if any database query was made while getting a related field
        if post_num_queries > pre_num_queries:
            field_name = self.get_field_name(descriptor_instance)

            if not field_name:
                logging.debug('N+1: cannot figure out field name')
                return related_model

            for file, line, function, statement in extract_stack():
                if field_name in statement:
                    logging.warning(
                        'N+1 for [model: {}, field: {}] \n\t'
                        '[file]: {}, [function]: {}, [statement]: {}, [line]: {}'.format(
                            model.__class__.__name__, field_name, file, function, statement, line
                        )
                    )
                    break

        return related_model


def show_nplusones():
    """
    Decorate Django's descriptors' __get__ method to log any N+1 candidate statements
    """

    descriptors = [ForwardManyToOneDescriptor, ForwardOneToOneDescriptor, ReverseOneToOneDescriptor]
    for descriptor in descriptors:
        get_method = getattr(descriptor, '__get__')
        setattr(descriptor, '__get__', NPlusOne(get_method))
