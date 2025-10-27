// =========================== Sales Statistic Line Chart Start ===============================
let salesChartInstance = null;
let donutChartInstance = null;
let paymentStatusChartInstance = null;
let barChartInstance = null; // NEW: manages #barChart lifecycle

function renderSalesChart(period = 'yearly') {
  fetch(`/api/sales-data/?period=${encodeURIComponent(period)}`)
    .then(response => response.json())
    .then(data => {
      if (data.error) {
        console.error("Error fetching sales data:", data.error);
        return;
      }

      const lineChartOptions = {
        series: [
          {
            name: "Sales",
            data: Array.isArray(data.data) ? data.data : []
          }
        ],
        chart: {
          height: 200,
          type: 'line',
          toolbar: { show: false },
          zoom: { enabled: false },
          dropShadow: {
            enabled: true,
            top: 6,
            left: 0,
            blur: 4,
            color: "#000",
            opacity: 0.1
          }
        },
        dataLabels: { enabled: false },
        stroke: {
          curve: 'smooth',
          colors: ['#487FFF'],
          width: 3
        },
        markers: {
          size: 0,
          strokeWidth: 3,
          hover: { size: 8 }
        },
        tooltip: {
          enabled: true,
          x: { show: true },
          y: {
            formatter: function (val) {
              return "$" + val + "k";
            }
          }
        },
        grid: {
          row: { colors: ['transparent', 'transparent'], opacity: 0.5 },
          borderColor: '#D1D5DB',
          strokeDashArray: 3
        },
        yaxis: {
          labels: {
            formatter: function (value) { return "$" + value + "k"; },
            style: { fontSize: "14px" }
          }
        },
        xaxis: {
          categories: Array.isArray(data.labels) ? data.labels : [],
          tooltip: { enabled: false },
          labels: {
            formatter: function (value) { return value; },
            style: { fontSize: "14px" }
          },
          axisBorder: { show: false },
          crosshairs: {
            show: true,
            width: 20,
            stroke: { width: 0 },
            fill: {
              type: 'solid',
              color: 'rgba(72,127,255,0.25)'
            }
          }
        }
      };

      const chartElement = document.querySelector("#chart");
      if (chartElement && typeof ApexCharts !== 'undefined') {
        if (salesChartInstance) {
          salesChartInstance.destroy();
          salesChartInstance = null;
        }
        salesChartInstance = new ApexCharts(chartElement, lineChartOptions);
        salesChartInstance.render();
      }
    })
    .catch(error => {
      console.error("Error fetching sales data:", error);
    });
}
// =========================== Sales Statistic Line Chart End ===============================

// ================================ Payment Status (CPV data) bar chart Start ================================ 
function renderPaymentStatusFromCPV() {
  fetch('/api/cpv-data/')
    .then(response => response.json())
    .then(data => {
      if (data.error) {
        console.error("Error fetching CPV data:", data.error);
        return;
      }

      const labels = Array.isArray(data.labels) ? data.labels : [];
      const values = Array.isArray(data.data) ? data.data : [];

      const paymentStatusOptions = {
        series: [{
          name: "Преизчислена стойност в Евро",
          data: values.map(v => Number(v) || 0)
        }],
        chart: {
          type: 'bar',
          height: 250,
          toolbar: { show: false }
        },
        plotOptions: {
          bar: {
            borderRadius: 6,
            horizontal: false,
            columnWidth: '52%',
            endingShape: 'rounded'
          }
        },
        dataLabels: { enabled: false },
        fill: {
          type: 'gradient',
          colors: ['#dae5ff'],
          gradient: {
            shade: 'light',
            type: 'vertical',
            shadeIntensity: 0.5,
            gradientToColors: ['#dae5ff'],
            inverseColors: false,
            opacityFrom: 1,
            opacityTo: 1,
            stops: [0, 100]
          }
        },
        grid: {
          show: true,
          borderColor: '#D1D5DB',
          strokeDashArray: 4,
          position: 'back',
          padding: { top: 0, right: 0, bottom: 0, left: 0 }
        },
        xaxis: {
          type: 'category',
          categories: labels
        },
        yaxis: {
          labels: {
            formatter: function (val) {
              const n = Number(val) || 0;
              return n >= 1000 ? (n / 1000).toFixed(0) + 'k' : String(n);
            }
          }
        },
        tooltip: {
          y: {
            formatter: function (val) {
              const n = Number(val) || 0;
              return n.toLocaleString('bg-BG') + " €";
            }
          }
        }
      };

      const el = document.querySelector("#paymentStatusChart");
      if (el && typeof ApexCharts !== 'undefined') {
        if (paymentStatusChartInstance) {
          paymentStatusChartInstance.destroy();
          paymentStatusChartInstance = null;
        }
        paymentStatusChartInstance = new ApexCharts(el, paymentStatusOptions);
        paymentStatusChartInstance.render();
      }
    })
    .catch(error => {
      console.error("Error fetching CPV data:", error);
    });
}
// ================================ Payment Status (CPV data) bar chart End ================================ 

// ================================ Bar chart: Executors per year into #barChart ================================ 
function renderExecutorsPerYearBarChart() {
  fetch('/api/executors-per-year/')
    .then(response => response.json())
    .then(data => {
      if (!data || data.error) {
        console.error("Error fetching executors-per-year data:", data && data.error);
        return;
      }
      const labels = Array.isArray(data.labels) ? data.labels : [];
      const values = Array.isArray(data.data) ? data.data.map(v => Number(v) || 0) : [];

      const options = {
        series: [{ name: "Брой изпълнители", data: values }],
        chart: { type: 'bar', height: 235, toolbar: { show: false } },
        plotOptions: { bar: { borderRadius: 6, horizontal: false, columnWidth: '52%', endingShape: 'rounded' } },
        dataLabels: { enabled: false },
        fill: {
          type: 'gradient',
          colors: ['#dae5ff'],
          gradient: { shade: 'light', type: 'vertical', shadeIntensity: 0.5,
            gradientToColors: ['#dae5ff'], inverseColors: false, opacityFrom: 1, opacityTo: 1, stops: [0, 100] }
        },
        grid: { show: false, borderColor: '#D1D5DB', strokeDashArray: 4, position: 'back',
          padding: { top: -10, right: -10, bottom: -10, left: -10 } },
        xaxis: { type: 'category', categories: labels },
        yaxis: {
          labels: { formatter: val => parseInt(val, 10).toString() }
        },
        tooltip: { y: { formatter: val => parseInt(val, 10).toLocaleString('bg-BG') } }
      };

      const el = document.querySelector("#barChart");
      if (el && typeof ApexCharts !== 'undefined') {
        if (barChartInstance) { barChartInstance.destroy(); barChartInstance = null; }
        barChartInstance = new ApexCharts(el, options);
        barChartInstance.render();
      }
    })
    .catch(error => console.error("Error fetching executors-per-year:", error));
}
// ============================================================================================================

// ================================ Users Overview Donut chart Start ================================ 
function renderRiskyMeanDonut() {
  fetch('/api/risky-mean/')
    .then(response => response.json())
    .then(data => {
      if (data.error) {
        console.error("Error fetching risky-mean data:", data.error);
        return;
      }
      if (!Array.isArray(data.labels) || !Array.isArray(data.data) || data.labels.length !== data.data.length) {
        console.error("Invalid risky-mean payload:", data);
        return;
      }

      const labels = data.labels;
      const values = data.data.map(v => Number(v) || 0);

      // Dynamic colors: values in [40, 60] -> red, others use palette
      const basePalette = ['#487FFF', '#6EE7B7', '#F59E0B', '#93C5FD', '#F472B6', '#A78BFA', '#10B981', '#60A5FA', '#FCD34D'];
      const colors = values.map((v, i) => {
        if (v >= 40 && v <= 60) return '#EF4444'; // red
        return basePalette[i % basePalette.length];
      });

      const donutOptions = {
        series: values,
        labels: labels,
        colors: colors,
        legend: { show: false },
        chart: {
          type: 'donut',
          height: 270,
          sparkline: { enabled: true }
        },
        stroke: { width: 0 },
        dataLabels: {
          enabled: true,
          formatter: function (val, opts) {
            const label = opts.w.globals.labels[opts.seriesIndex] || '';
            return label; // label inside each slice
          },
          style: {
            fontSize: '12px',
            fontWeight: 500
          },
          dropShadow: {
            enabled: false
          }
        },
        tooltip: {
          y: {
            formatter: function (val, opts) {
              const v = Number(val) || 0;
              const label = opts.w.globals.labels[opts.seriesIndex] || '';
              return label + ': ' + v.toLocaleString('en-US');
            }
          }
        },
        plotOptions: {
          pie: {
            donut: {
              size: '70%',
              labels: {
                show: false // center labels off; we render labels on slices instead
              }
            },
            dataLabels: {
              offset: 0,
              minAngleToShowLabel: 8
            }
          }
        },
        responsive: [{
          breakpoint: 480,
          options: {
            chart: { height: 220 },
            dataLabels: {
              style: { fontSize: '10px' }
            }
          }
        }]
      };

      const donutEl = document.querySelector("#userOverviewDonutChart");
      if (donutEl && typeof ApexCharts !== 'undefined') {
        if (donutChartInstance) {
          donutChartInstance.destroy();
          donutChartInstance = null;
        }
        donutChartInstance = new ApexCharts(donutEl, donutOptions);
        donutChartInstance.render();
      }
    })
    .catch(error => {
      console.error("Error fetching /api/risky-mean/:", error);
    });
}
// ================================ Users Overview Donut chart End ================================ 

// ================================ J Vector Map Start ================================ 
function renderWorldMap() {
  const worldMapElement = window.jQuery ? window.jQuery('#world-map') : null;
  if (worldMapElement && worldMapElement.length && typeof worldMapElement.vectorMap === 'function') {
    worldMapElement.vectorMap({
      map: 'world_mill_en',
      backgroundColor: 'transparent',
      borderColor: '#fff',
      borderOpacity: 0.25,
      borderWidth: 0,
      color: '#000000',
      regionStyle: {
        initial: {
          fill: '#D1D5DB'
        }
      },
      markerStyle: {
        initial: {
          r: 5,
          fill: '#fff',
          'fill-opacity': 1,
          stroke: '#000',
          'stroke-width': 1,
          'stroke-opacity': 0.4
        }
      },
      markers: [
        { latLng: [35.8617, 104.1954], name: 'China : 250' },
        { latLng: [25.2744, 133.7751], name: 'Australia : 250' },
        { latLng: [36.77,   -119.41],  name: 'USA : 82%' },
        { latLng: [55.37,   -3.41],    name: 'UK : 250' },
        { latLng: [25.20,   55.27],    name: 'UAE : 250' }
      ],
      series: {
        regions: [{
          values: {
            US: '#487FFF',
            SA: '#487FFF',
            AU: '#487FFF',
            CN: '#487FFF',
            GB: '#487FFF'
          },
          attribute: 'fill'
        }]
      },
      hoverOpacity: null,
      normalizeFunction: 'linear',
      zoomOnScroll: false,
      scaleColors: ['#000000', '#000000'],
      selectedColor: '#000000',
      selectedRegions: [],
      enableZoom: false,
      hoverColor: '#fff'
    });
  }
}
// ================================ J Vector Map End ================================ 

// ================================ Bootstrapping ================================ 
document.addEventListener('DOMContentLoaded', function () {
  // Sales chart initial render & select binding
  renderSalesChart('yearly');
  const salesPeriodSelect = document.querySelector('.form-select.bg-base.form-select-sm.w-auto');
  if (salesPeriodSelect) {
    salesPeriodSelect.addEventListener('change', function () {
      renderSalesChart(String(this.value || '').toLowerCase());
    });
  }

  // Keep Payment Status with CPV data
  renderPaymentStatusFromCPV();

  // Executors per year -> #barChart
  renderExecutorsPerYearBarChart();

  // Other components
  renderRiskyMeanDonut();
  renderWorldMap();
});
