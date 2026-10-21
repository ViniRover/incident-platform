"""Application errors: presentation adapters choose how to represent them."""


class ApplicationError(Exception):
    pass


class Conflict(ApplicationError):
    pass


class NotFound(ApplicationError):
    pass


class Forbidden(ApplicationError):
    pass


class Unauthenticated(ApplicationError):
    pass


class RateLimited(ApplicationError):
    pass


class DependencyUnavailable(ApplicationError):
    pass
