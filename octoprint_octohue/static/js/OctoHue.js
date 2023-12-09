/*
 * View model for OctoPrint-OctoHue
 *
 * Author: Entrippy
 * License: AGPLv3
 */
$(function() {
 
    ko.extenders.defaultIfNull = function(target, defaultValue) {
        var result = ko.computed({
            read: target,
            write: function(newValue) {
                if (!newValue) {
                    target(defaultValue);
                } else {
                    target(newValue);
                }
            }
        });
    
        result(target());
    
        return result;
    };

    function OctohueViewModel(parameters) {
        var self = this;
  
        self.settingsViewModel = parameters[0];
        self.selectedEvent = ko.observable();
        self.ownSettings = {};
        self.statusDict = [];

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

        self.addNewStatus = function () {
            var statusObj = {
                event: ko.observable(''),
                colour: ko.observable(''),
                brightness: ko.observable('').extend({ defaultIfNull: "255" }),
                delay: ko.observable('').extend({ defaultIfNull: "0" }),
                turnoff: ko.observable('')
            };
            self.ownSettings.statusDict.push(statusObj);
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

        self.bridgestatus = function() {
            OctoPrint.simpleApiCommand("octohue", "bridge", {"getstatus": "true"}, {});
        }

        self.bridgediscovery = function() {
            var search_button = this
		    search_button.innerHTML = '<i class="fa fa-search"></i> Searching...';
		    search_button.disabled = true;
		    document.getElementById("huebridge_searchstatus").style.display = "none";
		    document.getElementById("huebridge_found").style.display = "none";
            //OctoPrint.simpleApiCommand("octohue", "bridge", {"discover": "true"}, {});
            $.ajax({
				url: API_BASEURL + "plugin/octohue",
				type: "GET",
				dataType: "json",
				data: {command:"bridge", discover:true},
				contentType: "application/json; charset=UTF-8"
			}).done(function(data){
				if(data.internalipaddress){

                    bridgeaddr = data.internalipaddress + ":" + data.internalport;
					search_button.innerHTML = '<i class="fa fa-search"></i> Search my bridge';
					search_button.disabled = false;
					document.getElementById("huebridge_searchstatus").style.display = "";
					document.getElementById("huebridge_searchstatus").innerHTML = "<font color='green'>Brige found (<i>"+ data.internalipaddress+ ":" + data.internalport + "</i>) !</font>";
					document.getElementById("huebridge_found").style.display = "";
				}
			});

        }
 
        self.onBeforeBinding = function () {
            self.settings = self.settingsViewModel.settings;
            self.ownSettings = self.settings.plugins.octohue;
            self.statusDict = self.settingsViewModel.settings.plugins.octohue.statusDict;
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
