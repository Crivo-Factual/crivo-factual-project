"""Cliente da Instagram Graph API (M4).

Requer conta empresarial + app Meta + token (ver DEVELOPMENT.md).
Sem credenciais, o distribuidor salva a mensagem no outbox como
pendente manual. Nunca posta sem --live.
"""

import json
import os
import urllib.parse
import urllib.request


class InstagramClient:
    """Cliente mínimo: cria o contêiner de mídia e publica."""

    def __init__(self, user_id=None, access_token=None,
                 base_url="https://graph.instagram.com"):
        self.user_id = user_id or os.environ.get("IG_USER_ID", "")
        self.token = access_token or os.environ.get("IG_ACCESS_TOKEN", "")
        if not self.user_id or not self.token:
            raise ValueError(
                "IG_USER_ID e IG_ACCESS_TOKEN são obrigatórios "
                "(ver DEVELOPMENT.md, seção Distribuição)."
            )
        self.base_url = base_url.rstrip("/")

    def _post(self, path, payload):
        data = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + path,
            data=data,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def create_container(self, image_url, caption):
        if not image_url:
            raise ValueError("Instagram exige uma imagem pública (image_url).")
        data = self._post(
            f"/{self.user_id}/media",
            {
                "image_url": image_url,
                "caption": caption,
                "access_token": self.token,
            },
        )
        return data["id"]

    def publish_container(self, creation_id):
        data = self._post(
            f"/{self.user_id}/media_publish",
            {"creation_id": creation_id, "access_token": self.token},
        )
        return data["id"]

    def publish(self, image_url, caption):
        return self.publish_container(self.create_container(image_url, caption))
