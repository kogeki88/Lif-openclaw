module.exports = {
  apps: [
    {
      name: "shelter-bot",
      script: "python3",
      args: "/home/lifadmin/.openclaw/workspace-shelter/runtime/bot.py",
      cwd: "/home/lifadmin/.openclaw/workspace-shelter",
      env_file: "/home/lifadmin/.openclaw/workspace-shelter/.env",
      autorestart: true,
      max_restarts: 20,
      restart_delay: 3000,
      out_file: "/home/lifadmin/.openclaw/workspace-shelter/logs/shelter.log",
      error_file: "/home/lifadmin/.openclaw/workspace-shelter/logs/shelter.log",
    },
  ],
};
