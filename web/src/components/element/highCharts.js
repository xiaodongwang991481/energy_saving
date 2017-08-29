import React from "react"

import Highcharts from "highcharts"

export default class HighChartsComponent extends React.Component{
    constructor(props){
        super(props);
        this.chartContainer = null;
        this.chart = null;

    }

    componentDidMount(){
        let chartOpts = this.props || {};
        this.chart = Highcharts.chart(this.chartContainer, {
            chart: {
                zoomType: 'x'
            },
            title: {
                text: chartOpts.title || "title"
            },
            // subtitle: {
            //     text: document.ontouchstart === undefined ?
            //         'Click and drag in the plot area to zoom in' : 'Pinch the chart to zoom in'
            // },
            xAxis: {
                type: 'datetime'
            },
            yAxis: {
                title: {
                    text: chartOpts.yTitle || ""
                }
            },
            // legend: {
            //     layout: 'vertical',
            //     align: 'right',
            //     verticalAlign: 'middle'
            // },
            plotOptions: {
                // area: {
                //     fillColor: {
                //         linearGradient: {
                //             x1: 0,
                //             y1: 0,
                //             x2: 0,
                //             y2: 1
                //         },
                //         stops: [
                //             [0, Highcharts.getOptions().colors[0]],
                //             [1, Highcharts.Color(Highcharts.getOptions().colors[0]).setOpacity(0).get('rgba')]
                //         ]
                //     },
                //     marker: {
                //         radius: 2
                //     },
                //     lineWidth: 1,
                //     states: {
                //         hover: {
                //             lineWidth: 1
                //         }
                //     },
                //     threshold: null
                // }
            },

            series:this.props.series
        });
    }

    componentWillUnmount(){
        if(this.chart){
            this.chart.destroy();
        }
    }

    componentWillUpdate(nextProps, nextState){
        if(this.props.series != nextProps.series){
            this.chart.series = nextProps.series;
        }

    }



    render(){
        return(
            <div id="container" ref={(container)=>{this.chartContainer = container}}>ChartsComponent</div>
        )
    }
}