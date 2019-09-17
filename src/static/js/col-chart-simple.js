function drawSimpleColChart(elementId, dataList, titleStr) {
    var data = google.visualization.arrayToDataTable(dataList);

    var view = new google.visualization.DataView(data);
    view.setColumns([0, 1]);

    var options = {
        title: titleStr,
        legend: { position: "none" },
        vAxis: {minValue: 0}
    };
    var chart = new google.visualization.ColumnChart(document.getElementById(elementId));
    chart.draw(view, options);
}
