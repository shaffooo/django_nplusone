import logging
import re

from django.db import connections
from django.db.models.fields.related_descriptors import (ForwardManyToOneDescriptor, ForwardOneToOneDescriptor,
                                                         ReverseOneToOneDescriptor, ReverseManyToOneDescriptor,
                                                         ManyToManyDescriptor)

from traceback import extract_stack


# to prevent an error message being output to sys.stderr in the absence of logging configuration
logging.getLogger('nplusone').addHandler(logging.NullHandler())


class NPlusOne:
    """
    Class decorator to wrap around Django's related field descriptors' __get__ method

    Django uses forward/reverse descriptors for a field to get related models from cache, if present, or make a database
    query for current model record. This class wraps the descriptors __get__ method with a decorator to find out if a
    database query was made or not. If Django made a database query this will probably lead to N+1 queries so decorator
    will detect that and print a debug message to alert developer.
    """

    WARNING_MSG_FORMAT = '\n*** Possible N+1 for model: {model}, field: {field},\nrelationship: {relationship},'\
        '\nfile: {file}, \nfunction: {function}, line: {line}, statement: {statement}\n'

    DESCRIPTOR = 'Descriptor'

    IGNORE_WARNING_CODE = '# NO-NPLUSONE'

    def __init__(self, get_method):
        self.get_method = get_method

        # keep track of reported warnings to avoid re-reporting for every model instance
        self.reported_warnings = set()

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

        # if model is None, don't proceed
        if not model:
            return related_model

        # make sure we can get a field name from descriptor
        field_name = self.get_field_name(descriptor_instance)
        if not field_name:
            return related_model

        if post_num_queries > pre_num_queries:
            self.report_warning(model_name=model.__class__.__name__, field_name=field_name,
                                relationship=self.get_relationship_from_descriptor(descriptor_instance))

        # for ReverseManyToOneDescriptor and ManyToManyDescriptor, only RelatedManager and ManyRelatedManager are
        # returned respectively. The actual decision to make database query or not is done at queryset level
        if type(descriptor_instance) in [ReverseManyToOneDescriptor, ManyToManyDescriptor]:

            # related_model is actually a RelatedManager/ManyRelatedManager in this case
            prefetch_pre_num_queries = self.total_queries()
            list(related_model.all())
            prefetch_post_num_queries = self.total_queries()

            if prefetch_post_num_queries > prefetch_pre_num_queries:
                self.report_warning(model_name=model.__class__.__name__, field_name=field_name,
                                    relationship=self.get_relationship_from_descriptor(descriptor_instance))

        return related_model

    def report_warning(self, model_name, field_name, relationship):
        """
        Use call stack to trace the statement responsible for N+1 and log it if applicable
        """
        for file, line, function, statement in extract_stack():
            if re.search(r'\b{field_name}\b'.format(field_name=re.escape(field_name)), statement):
                self.log_warning(model=model_name, field=field_name, relationship=relationship,
                                 file=file, function=function, line=line, statement=statement)
                break

    def log_warning(self, **kwargs):
        """
        Keep track of reported warnings to avoid repeated warnings for same statement when used in iteration
        """

        # ignore warning for statement if it contains the IGNORE_WARNING_CODE
        statement = kwargs.get('statement')
        if self.ignore_warning_for_statement(statement):
            return

        # construct warning message
        message = self.WARNING_MSG_FORMAT.format(**kwargs)

        if message in self.reported_warnings:
            return

        # otherwise, record the warning and log it
        self.reported_warnings.add(message)
        logging.warning(message)

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

        if isinstance(descriptor_instance, ReverseOneToOneDescriptor):
            return descriptor_instance.related.name

        many_descriptors = [ReverseManyToOneDescriptor, ManyToManyDescriptor]
        if any(isinstance(descriptor_instance, descriptor_class) for descriptor_class in many_descriptors):

            related_name = descriptor_instance.rel.related_name
            if related_name:
                return related_name

            return '{}_set'.format(descriptor_instance.rel.name)

        # since this message is meant to be used as advice, we can't throw exception
        return None

    def ignore_warning_for_statement(self, statement):
        """
        Ignore reporting warning for a statement that ends with comment IGNORE_WARNING_CODE
        """

        if statement.strip().endswith(self.IGNORE_WARNING_CODE):
            return True

        return False

    def get_relationship_from_descriptor(self, descriptor):
        """
        Get relationship from descriptor type by stripping `Descriptor` off from end
        """
        descriptor_class_name = descriptor.__class__.__name__

        if descriptor_class_name.endswith(self.DESCRIPTOR):
            return descriptor_class_name[:-len(self.DESCRIPTOR)]

        return descriptor_class_name


def show_nplusones():
    """
    Decorate Django's descriptors' __get__ method to log any N+1 candidate statements
    """

    # ManyToManyDescriptor is subclass of ReverseManyToOneDescriptor with no __get__ method of its own
    descriptors = [ForwardManyToOneDescriptor, ForwardOneToOneDescriptor, ReverseOneToOneDescriptor,
                   ReverseManyToOneDescriptor]

    for descriptor in descriptors:
        get_method = getattr(descriptor, '__get__')
        setattr(descriptor, '__get__', NPlusOne(get_method))
