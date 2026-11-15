"""A small name-to-factory registry, shared by readers and writers."""

from collections.abc import Callable

from anyaudiobook.errors import UnsupportedFormatError


class Registry[T]:
    """Map names (file suffixes, format names) to factories building a ``T``.

    Readers are registered under file suffixes (``.epub``), writers under
    format names (``m4b``). Names are matched ignoring case, so new formats
    can be plugged in without touching the code that looks them up::

        READERS.register(Fb2Reader, ".fb2")
    """

    def __init__(self, kind: str) -> None:
        """Create an empty registry.

        Args:
            kind: What the registry holds, used in error messages
                (e.g. ``"input format"``).
        """
        self._kind = kind
        self._factories: dict[str, Callable[[], T]] = {}

    def register(self, factory: Callable[[], T], *names: str) -> None:
        """Make ``factory`` the one to use for each of ``names``.

        A name registered before is overridden, so a custom implementation
        can replace a built-in one.
        """
        for name in names:
            self._factories[name.lower()] = factory

    def create(self, name: str) -> T:
        """Build the object registered under ``name``.

        Raises:
            UnsupportedFormatError: If nothing is registered under ``name``.
        """
        factory = self._factories.get(name.lower())
        if factory is None:
            raise UnsupportedFormatError(
                f"Unsupported {self._kind} {name!r}; supported: {', '.join(self.names)}"
            )
        return factory()

    @property
    def names(self) -> tuple[str, ...]:
        """The registered names, sorted."""
        return tuple(sorted(self._factories))

    def __contains__(self, name: object) -> bool:
        """Return True if something is registered under ``name``."""
        return isinstance(name, str) and name.lower() in self._factories
