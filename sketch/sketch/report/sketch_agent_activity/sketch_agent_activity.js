// Copyright (c) 2026, Faris Ansari and contributors
// For license information, please see license.txt

frappe.query_reports["Sketch Agent Activity"] = {
	filters: [
		{
			fieldname: "days",
			label: __("Window (days)"),
			fieldtype: "Int",
			default: 7,
			reqd: 1,
		},
	],
	// A row that failed is the reason to open this report, so it must be
	// readable at a glance and not a number to hunt for.
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "not_ok" && data && data.not_ok > 0) {
			value = `<span style="color: var(--text-on-red, #b91c1c)">${value}</span>`;
		}
		return value;
	},
};
