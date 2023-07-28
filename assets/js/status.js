function checkStatus(url, callback) {
    fetch(url, {
        method: 'GET',
        mode: 'no-cors'
    }).then(function(response) {
        callback('up');
    }
    ).catch(function(error) {
        callback('down');
    }
    );
}

// Check every 5 seconds
setInterval(function() {
   checkStatuses();
}, 5000);

function checkStatuses(){
    checkStatus('https://nathan.woodburn.au', function(updateStatus) {
        if (updateStatus == 'up') document.getElementById('nathan-woodburn-au').style.color = '#00ff00';
        else document.getElementById('nathan-woodburn-au').style.color = '#ff0000';
    });
    checkStatus('https://nathan3dprinting.au', function(updateStatus) {
        if (updateStatus == 'up') document.getElementById('nathan3dprinting-au').style.color = '#00ff00';
        else document.getElementById('nathan3dprinting-au').style.color = '#ff0000';
    });
    checkStatus('https://podcast.woodburn.au', function(updateStatus) {
        if (updateStatus == 'up') document.getElementById('podcast-woodburn-au').style.color = '#00ff00';
        else document.getElementById('podcast-woodburn-au').style.color = '#ff0000';
    });
    checkStatus('https://uptime.woodburn.au', function(updateStatus) {
        if (updateStatus == 'up') document.getElementById('uptime-woodburn-au').style.color = '#00ff00';
        else document.getElementById('uptime-woodburn-au').style.color = '#ff0000';
    });
    checkStatus('https://reg.woodburn.au', function(updateStatus) {
        if (updateStatus == 'up') document.getElementById('reg-woodburn-au').style.color = '#00ff00';
        else document.getElementById('reg-woodburn-au').style.color = '#ff0000';
    });
    checkStatus('https://hnscall', function(updateStatus) {
        if (updateStatus == 'up') document.getElementById('hnscall').style.color = '#00ff00';
        else document.getElementById('hnscall').style.color = '#ff0000';
    });
    checkStatus('https://hnshosting', function(updateStatus) {
        if (updateStatus == 'up') document.getElementById('hnshosting').style.color = '#00ff00';
        else document.getElementById('hnshosting').style.color = '#ff0000';
    });
}

// Check on load
checkStatuses();