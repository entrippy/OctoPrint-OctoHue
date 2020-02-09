/*
 * View model for OctoPrint-OctoHue
 *
 * Author: Entrippy
 * License: AGPLv3
 */
$(function() {
    function OctohueViewModel(parameters) {
        var self = this;

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
        dependencies: [ /* "loginStateViewModel", "settingsViewModel" */ ],
        elements: [ "#navbar_plugin_octohue" ]
    });
});
