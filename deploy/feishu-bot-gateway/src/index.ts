import { createApp } from "./app.js";
import { loadConfig } from "./config.js";
import { createLogger } from "./logger.js";

const config = loadConfig();
const logger = createLogger(config.logLevel);
const app = createApp();

app.listen(config.port, () => {
  logger.info("feishu bot gateway started", { port: config.port });
});
