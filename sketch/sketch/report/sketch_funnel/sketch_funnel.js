// Copyright (c) 2026, Faris Ansari and contributors
// For license information, please see license.txt

frappe.query_reports["Sketch Funnel"] = {
	filters: [
		{
			fieldname: "days",
			label: __("Recent window (days)"),
			fieldtype: "Int",
			default: 7,
			reqd: 1,
		},
	],
	// The step is the row's identity, so the eye should land on it first. Grey
	// the rows that are not the funnel itself.
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "step") {
			value = `<span style="font-weight:500">${value}</span>`;
		}
		return value;
	},
};
