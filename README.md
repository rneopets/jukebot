# Jukebot

Small Discord bot to play music forever! _(bring your own music! Currently only supports `.mp3` files.)_

## Environment Variables

To run this project, you will need to add the following environment variables to your `.env` file: (see `.env.example`)

- `BOT_TOKEN` - [Your Discord bot's token.](https://discord.com/developers/applications)

## Deployment

Jukebot runs pm2-managed on the Vultr box at `/opt/bots/jukebot`
(`ecosystem.config.js` runs `docker compose up`).

Pushing a change to `Dockerfile`, `pyproject.toml`, `uv.lock`, or
`.dockerignore` on `master` triggers
`.github/workflows/build-deploy.yaml`, which builds and pushes
`ghcr.io/rneopets/jukebot` to GHCR, then SSHes into the Vultr box and runs
`git pull && docker compose pull && pm2 restart jukebot`. It can also be
run manually via `workflow_dispatch`.

Ordinary code-only changes (no Dockerfile/dependency changes) don't need
the Action at all - the container bind-mounts the repo (`./:/app` in
`docker-compose.yaml`), so a plain `git pull` + `pm2 restart jukebot` on
the box picks them up without a rebuild.

Required secrets on the repo: `VULTR_HOST`, `VULTR_SSH_USER`,
`VULTR_SSH_KEY`.

## Notes

- At the moment, this is hardcoded to work with one server and one channel within the server using their IDs. This may or may not change.

## Community Fanart

![Happy Bots](assets/happybots.jpg)
Drawn by **Mimble 🍄 - (One Umbrella#0520)**
