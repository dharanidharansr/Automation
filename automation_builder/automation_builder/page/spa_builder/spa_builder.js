frappe.pages["spa-builder"].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Automation Builder"),
		single_column: true,
	});

	page.body.empty();

	$('<div id="automation-builder-app"></div>').appendTo(page.body);

	// Inject CSS with cache busting to avoid stale browser cache
	var cssVersion = frappe.utils.get_filename_based_on_content
		? Date.now()
		: Date.now();
	var link = document.createElement("link");
	link.rel = "stylesheet";
	link.type = "text/css";
	link.href = "/assets/automation_builder/css/style.css?v=" + cssVersion;
	document.head.appendChild(link);

	frappe.require(
		[
			"assets/automation_builder/js/index.js",
		],
		function () {
			// Vue app auto-mounts via main.js
		}
	);
};
