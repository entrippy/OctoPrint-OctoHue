/*
 * View model for OctoPrint-OctoHue
 *
 * Author: Entrippy
 * License: AGPLv3
 */
$(function() {
    function OctohueViewModel(parameters) {
        var self = this;
  
        self.settingsViewModel = parameters[0];

        self.ownSettings = {}
        self.customstatus = {}

        self.obsstatus = []
        
        self.flattenstatus = function() {
            for (let ki=0; ki < Object.keys(self.customstatus).length; ki++ ) {
                self.statusobj = {};
                self.status = Object.keys(self.customstatus)[ki]
                self.statusobj.status = self.status
                for (let [key, value] of Object.entries(self.customstatus[self.status]) ) {
                    self.statusobj[key] = value
                }
                self.obsstatus.push(self.statusobj)
            }
        }

        self.addNewStatus = function() {
            
        }
        self.togglehue = function() {
            OctoPrint.simpleApiCommand("octohue", "togglehue", {}, {});
        }
 
        self.onBeforeBinding = function () {
            self.settings = self.settingsViewModel.settings;
            self.ownSettings = self.settings.plugins.octohue;
            self.customstatus = self.ownSettings.customstatus

            self.flattenstatus();

        }

        


    }

    /* view model class, parameters for constructor, container to bind to
     * Please see http://docs.octoprint.org/en/master/plugins/viewmodels.html#registering-custom-viewmodels for more details
     * and a full list of the available options.
     */
    OCTOPRINT_VIEWMODELS.push({
        construct: OctohueViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#settings_plugin_octohue", "#navbar_plugin_octohue"]
    })
})
