function drawPieChart(elementId, dataList, titleStr) {

    var data = google.visualization.arrayToDataTable(dataList);

    var bgColor = document.getElementById(elementId).style.backgroundColor;

    var options = {
        title: titleStr,
        backgroundColor: bgColor
    };

    var chart = new google.visualization.PieChart(document.getElementById(elementId));
    chart.draw(data, options);
}