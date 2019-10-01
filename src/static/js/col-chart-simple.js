function drawSimpleColChart(elementId, dataList, titleStr, drawLegend=false, stacked=false) {
    var data = google.visualization.arrayToDataTable(dataList);

    var view = new google.visualization.DataView(data);

    var options = {
        title: titleStr,
        legend: { position: "none" },
        vAxis: {minValue: 0},
        bar: { groupWidth: '75%' },
        isStacked: stacked
    };

    if (drawLegend) {
        options["legend"]["position"] = "top";
        options["legend"]["maxLines"] = 3;
    }

    var chart = new google.visualization.ColumnChart(document.getElementById(elementId));
    chart.draw(view, options);
}
