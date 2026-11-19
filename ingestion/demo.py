"""Fictional source tape. Offsets are seconds from the start of the replay day."""
SOURCES = [
    ("News search", "Syndicated headlines", "RSS"),
    ("Press wire", "Corporate announcements", "RSS"),
    ("Filings", "Executive departure notices", "EDGAR"),
    ("Social stream", "Public posts", "WS"),
    ("Business wire", "Publisher releases", "RSS"),
    ("News index", "Independent reporting", "DOC"),
]
# Offset, source, publisher, subject, headline, story text, kind, trusted, scan batch.
TAPE = [
    (51635, 0, "Northline Wire", "HLVD", "Halvorsen Dynamics schedules board meeting", "The directors are due to meet this afternoon.", "routine", False, 1712),
    (51740, 4, "Morrow Vale Pressroom", "MVL.D", "Morrow Vale opens a new regional office", "The office will support its distribution team.", "routine", False, 1206),
    (51828, 3, "Social stream", "TVG.D", "Post alleges a relationship involving Torven Grid CEO", "An uncorroborated post alleges Torven Grid CEO Elin Voss had an undisclosed relationship.", "social", False, 1640),
    (51920, 1, "Kestrel Nine Pressroom", "KSN.D", "Kestrel Nine publishes its quarterly outlook", "The company released updated guidance for its operations.", "routine", False, 1464),
    (52011, 5, "Meridian Ledger", "HLVD", "Halvorsen board confirms CEO relationship inquiry", "Halvorsen Dynamics confirmed its board reviewed an undisclosed relationship involving CEO Mark Brenner.", "report", True, 1228),
    (52103, 2, "Filing desk", "HLVD", "Halvorsen Dynamics files executive departure notice", "The fictional Item 5.02 notice records Mark Brenner’s departure from Halvorsen Dynamics. It gives no reason for the departure.", "filing", False, 860),
    (52158, 3, "Social stream", "KSN.D", "Post questions Kestrel Nine CEO disclosure", "A single post alleges Kestrel Nine CEO Luca Venn had an undisclosed relationship. No independent reporting is available.", "social", False, 1115),
    (52240, 4, "Morrow Vale Pressroom", "MVL.D", "Morrow Vale names a new head of corporate affairs", "Morrow Vale CEO Ada Tern announced a new corporate affairs appointment.", "routine", False, 1255),
    (52291, 0, "Civic Business", "TVG.D", "Torven Grid board reviews CEO disclosure", "Torven Grid says its board is reviewing a reported workplace relationship involving CEO Elin Voss.", "report", False, 1577),
    (52328, 0, "Northline Wire", "HLVD", "Halvorsen Dynamics CEO resigns after board review", "Halvorsen Dynamics CEO Mark Brenner resigned after the board confirmed an undisclosed workplace relationship.", "report", False, 789),
    (52349, 1, "Morrow Vale Pressroom", "MVL.D", "Morrow Vale schedules its annual shareholder meeting", "The annual shareholder meeting will take place next month.", "routine", False, 32),
    (52370, 4, "Kestrel Nine Pressroom", "KSN.D", "Kestrel Nine releases its operations update", "The release covers manufacturing capacity across its three divisions.", "routine", False, 27),
    (52398, 5, "Westhaven Journal", "TVG.D", "Second outlet confirms Torven Grid relationship review", "Independent reporting confirms Torven Grid is reviewing an undisclosed relationship involving CEO Elin Voss.", "report", False, 41),
    (52417, 0, "Meridian Ledger", "KSN.D", "Kestrel Nine confirms CEO disclosure inquiry", "Kestrel Nine confirms its board is investigating an undisclosed relationship involving CEO Luca Venn.", "report", True, 24),
]
INITIAL_FRAME = 9
