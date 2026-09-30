"""Composition-root adapter for private display URL signing."""

from probeinterview.platform.foundation.application.object_storage import (
    ObjectStorage,
    SignedObjectUrl,
)


class ObjectStorageAvatarSigner:
    """Sign short-lived display URLs through the shared storage port.

    Object keys stay inside the modules; every outbound display surface
    receives only bounded-lifetime signed URLs.
    """

    def __init__(self, storage: ObjectStorage) -> None:
        self._storage = storage

    def sign(self, object_key: str) -> SignedObjectUrl:
        return self._storage.sign_get_url(object_key=object_key)
