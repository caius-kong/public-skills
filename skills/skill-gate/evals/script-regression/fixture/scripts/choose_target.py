def choose_target(config, chats):
    return config.get("alert_target") or chats[0]
