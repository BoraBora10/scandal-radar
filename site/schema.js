import { sqliteTable, text, integer } from "drizzle-orm/sqlite-core";
export const dashboardState = sqliteTable("dashboard_state", {
  kind: text("kind").primaryKey(),
  revision: integer("revision").notNull(),
  payload: text("payload").notNull(),
});
