module.exports = {
  apps: [
    {
      name: "jukebot",
      script: "docker",
      args: ["compose", "up"],
      cwd: "/opt/bots/jukebot/",
      autorestart: true,
      restart_delay: 1000,
    },
  ],
};
