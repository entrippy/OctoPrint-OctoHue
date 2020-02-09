/*
 * View model for OctoPrint-OctoHue
 *
 * Author: Entrippy
 * License: AGPLv3
 */
$(function() {
    function OctohueViewModel(parameters) {
        var self = this;

        // assign the injected parameters, e.g.:
        // self.loginStateViewModel = parameters[0];
        // self.settingsViewModel = parameters[1];

        self.togglehue = function() {
            OctoPrint.simpleApiCommand("octohue", "togglehue", {}, {});
        };
    }

    /* view model class, parameters for constructor, container to bind to
     * Please see http://docs.octoprint.org/en/master/plugins/viewmodels.html#registering-custom-viewmodels for more details
     * and a full list of the available options.
     */
    OCTOPRINT_VIEWMODELS.push({
        construct: OctohueViewModel,
        // ViewModels your plugin depends on, e.g. loginStateViewModel, settingsViewModel, ...
        dependencies: [ /* "loginStateViewModel", "settingsViewModel" */ ],
        // dependencies: [ NavigationViewModel ],
        // Elements to bind to, e.g. #settings_plugin_OctoHue, #tab_plugin_OctoHue, ...
        elements: [ "#navbar_plugin_octohue" ]
    });
});
