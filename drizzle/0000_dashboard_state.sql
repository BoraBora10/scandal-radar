CREATE TABLE `dashboard_state` (
	`kind` text PRIMARY KEY NOT NULL,
	`revision` integer NOT NULL,
	`payload` text NOT NULL
);
