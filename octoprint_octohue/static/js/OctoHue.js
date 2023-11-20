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
        self.selectedEvent = ko.observable();
        self.ownSettings = {};
        self.statusDict = {};

        self.statusDetails = function (data) {
            if (data === false) {
                return {
                    event: ko.observable(""),
                    colour: ko.observable(""),
                    brightness: ko.observable(""),
                    delay: ko.observable(""),
                    turnoff: ko.observable(false)
                };
            
            } else {
                if (!data.hasOwnProperty("turnoff")) {
                    data["turnoff"] = ko.observable(true);
                }
                return data;
            }
        };

        self.statusDict = {}

        self.addNewStatus = function () {
            var statusObj = {
                status: ko.observable(''),
                colour: ko.observable(''),
                brightness: ko.observable(''),
                turnoff: ko.observable('')
            };
            self.statusDict.push(
                self.statusObj
            );
        }

        self.addStatus = function () {
            self.selectedEvent(self.statusDetails(false));
            self.settingsViewModel.settings.plugins.octohue.statusDict.push(
                self.selectedEvent()
            );
            $("#StatusManagerEditor").modal("show");
        };

        self.editStatus = function (data) {
            self.selectedEvent(self.statusDetails(data));
        };

        self.removeStatus = function (data) {
            self.settingsViewModel.settings.plugins.octohue.statusDict.remove(
                data
            );
        };

        self.setSwitchOff = function(status) {
            status.turnoff(!status.turnoff());
        };

        self.togglehue = function() {
            OctoPrint.simpleApiCommand("octohue", "togglehue", {}, {});
        }
 
        self.onBeforeBinding = function () {
            self.settings = self.settingsViewModel.settings;
            self.ownSettings = self.settings.plugins.octohue;
            self.statusDict = self.settingsViewModel.settings.plugins.octohue.statusDict;
        }
     
        self.onSettingsBeforeSave = function () {
            self.ownSettings.statusDict = self.statusDict;
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
