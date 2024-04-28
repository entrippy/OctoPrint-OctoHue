/*
 * View model for OctoPrint-OctoHue
 *
 * Author: Simon Beckett
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

        self.bridgediscovery = function() {
            var search_button = this
		    search_button.innerHTML = '<i class="fa fa-search"></i> Searching...';
		    search_button.disabled = true;
		    //document.getElementById("huebridge_searchstatus").style.display = "none";
		    //document.getElementById("huebridge_found").style.display = "none";
            OctoPrint.simpleApiCommand("octohue", "bridge", {"discover": "true"}, {}).done(function(response) {
				if(response[0].internalipaddress){
                    bridgeaddr = response[0].internalipaddress;
                    search_button.innerHTML = '<i class="fa fa-search"></i> Search my bridge';
					search_button.disabled = false;
					document.getElementById("huebridge_searchstatus").classList.remove("inactiveconfig");
					document.getElementById("huebridge_searchstatus").innerHTML = "<font color='green'>Brige found (<i>"+ response[0].internalipaddress+ "</i>) !</font>";
					document.getElementById("huebridge_found").classList.remove("inactiveconfig");
				}
			});
        };

        self.bridgepair = function() {
            var bridgebutton = document.getElementById("huebridge_pairingbutton");
		    bridgebutton.innerHTML = '<i class="fa fa-link"></i> Pairing...';
		    bridgebutton.disabled = true;
		    
            var pairing_try_count = 0;
		    var text_pairing_count = document.getElementById("huebridge_pairingreties");
		    text_pairing_count.innerHTML = "Try count: " + pairing_try_count + "/30";
		    document.getElementById("huebridge_startsearch").disabled = true;
		    var interval_pairing = setInterval(function() {
			pairing_try_count += 1;
			text_pairing_count.innerHTML = "Try count: " + pairing_try_count + "/30";
            
            OctoPrint.simpleApiCommand("octohue", "bridge", {"pair": "true", "bridgeaddr":bridgeaddr}, {}).done(function(response) {
				if(response[0].response == "success")
				{
                    clearInterval(interval_pairing);
					text_pairing_count.innerHTML = "<font color='green'>Succesfull Pairing !</font>";
                    setTimeout(function(){
                        self.getbridgestatus();
                        document.getElementById("bridgeaddress").value = response[0].bridgeaddr
                        document.getElementById("apikey").value = response[0].husername
                        document.getElementById("huebridgestatus").backgroundColor = "green";
                        document.getElementById("huebridgestatus").innerHTML = "Paired";
                    }, 5000);
				}
			})

			if(pairing_try_count == 30)
			{
				clearInterval(interval_pairing);
				pairing_bridge_button.innerHTML = '<i class="fa fa-link"></i> Start Pairing';
				pairing_bridge_button.disabled = false;
				text_pairing_count.innerHTML = "<font color='red'>Unable to pair. Please try again</font>";
				document.getElementById("huebridge_startsearch").disabled = false;
			}
		}, 1000);
        };
    
        self.getbridgestatus = function() {
            OctoPrint.simpleApiCommand("octohue", "bridge", {"getstatus": "true"}, {}).done(function(response) {
                if ( response.bridgestatus === "configured") {
                    document.getElementById("huebridge_unconfigured").classList.add("inactiveconfig")
                    document.getElementById("huebridge_configured").classList.remove("inactiveconfig")
                } else if (response.bridgestatus === "unconfigured") {
                    document.getElementById("huebridge_configured").classList.add("inactiveconfig")
                    document.getElementById("huebridge_unconfigured").classList.remove("inactiveconfig")
                }
                
            });
        };

        self.getDevices = function (data) {
            return OctoPrint.simpleApiCommand("octohue", "getdevices", {"archetype": data}, {})
                .then(response => response.devices); // Access devices from successful response
        };
          
        self.getDevices("plug").then(devices => {
            self.huePlugs = devices;
        }).catch(error => {
            console.error("Error fetching devices:", error);
            }
        );

        self.onBeforeBinding = function () {
            self.settings = self.settingsViewModel.settings;
            self.ownSettings = self.settings.plugins.octohue;
            self.statusDict = self.settingsViewModel.settings.plugins.octohue.statusDict;
        };

        self.onSettingsShown = function () {
           self.getbridgestatus() 
        };

        self.removeStatus = function (data) {
            self.settingsViewModel.settings.plugins.octohue.statusDict.remove(
                data
            );
        };

        self.setSwitchOff = function(status) {
            status.turnoff(!status.turnoff());
        };

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

        self.togglehue = function() {
            OctoPrint.simpleApiCommand("octohue", "togglehue", {}, {});
        };


    };

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
