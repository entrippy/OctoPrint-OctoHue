/*
 * View model for OctoPrint-OctoHue
 *
 * Author: Entrippy
 * License: AGPLv3
 */
$(function() {
    function OctohueViewModel(parameters) {
        ko.extenders.stripQuotes = function(target, opts) {
            const result = ko.pureComputed({
                read: target,
                write: function(newVal) {
                    const stripped = newVal.replace(/['"]+/g, '')
                    target(stripped)
                }
            }).extend({ notify: 'always' });
            result(target())
            return result;
        }

        var self = this;
  
        self.settingsViewModel = parameters[0];


        self.ownSettings = {}
        self.statusDict = {}
        self.nestedStatus = {}

        self.flatStatus = ko.observableArray()
        
        self.flattenstatus = function(nestedStatuses) {
            for (let ki=0; ki < Object.keys(nestedStatuses).length; ki++ ) {
                var statusObj = {};
                var status = Object.keys(nestedStatuses)[ki]
                statusObj.status = status
                for (let [key, value] of Object.entries(nestedStatuses[status]) ) {
                    statusObj[key] = value
                }
                self.flatStatus.push(statusObj)
            }
            return self.flatStatus
        }

        self.nestStatus = function(newStatuses) {
            for (let i=0; i < newStatuses().length; i++ ) {
                if (ko.isObservable(newStatuses()[i].status)) {
                    self.nestedStatus[newStatuses()[i].status()] = {
                        colour: newStatuses()[i].colour(),
                        brightness: newStatuses()[i].brightness(),
                        delay: newStatuses()[i].delay(),
                        turnoff: newStatuses()[i].turnoff()
                    }
                } else { 
                    self.nestedStatus[newStatuses()[i].status] = {
                        colour: newStatuses()[i].colour,
                        brightness: newStatuses()[i].brightness,
                        delay: newStatuses()[i].delay,
                        turnoff: newStatuses()[i].turnoff
                    }
                }
            }
            return self.nestedStatus
        }

        self.addNewStatus = function() {
            var statusObj = {
                status: ko.observable(''),
                colour: ko.observable(''),
                brightness: ko.observable(''),
                delay: ko.observable(''),
                turnoff: ko.observable('')
            };

            self.flatStatus.push(statusObj)
        }

        self.onStatusDictDelete = function (status) {
            self.flatStatus.remove(status)
        }

        self.setSwitchOff = function(status) {
            status.turnoff(!status.turnoff());
        };

        self.togglehue = function() {
            OctoPrint.simpleApiCommand("octohue", "togglehue", {}, {});
        }
 
        self.onBeforeBinding = function () {
            self.settings = self.settingsViewModel.settings;
            self.ownSettings = self.settings.plugins.octohue;
            self.statusDict = self.ownSettings.statusDict

            self.flatStatus = self.flattenstatus(self.statusDict);
            self.flatStatus.extend({
                rateLimit: 50,
            });
        }

        self.onSettingsBeforeSave = function () {
            str = JSON.stringify(self.flatStatus)
            console.log(self.flatStatus)
            self.ownSettings.statusDict = self.nestStatus(self.flatStatus);
            str = JSON.stringify(self.ownSettings.statusDict)
            console.log(self.ownSettings.statusDict)
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
