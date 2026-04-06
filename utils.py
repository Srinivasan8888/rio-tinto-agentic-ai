import numpy as np
import matplotlib.pyplot as plt

def interactive_code(y,limit,gate):   
    dt = 1/125
    figg, axs = plt.subplots(1,1,figsize=(9,6))
##    ax.append(figg.add_subplot(2,1,1))
##    ax.append(figg.add_subplot(2,1,2))
    axs.set_title('Peak & valley track')
    axs.set_xlabel('Time(s)')
    axs.set_ylabel('Amplitude')
    axs.plot(y,picker=True,pickradius=1,label='Amplitude')
    time1=[]
    Average=[]
    indice = []



    def onpick(event):
        thisline = event.artist
        print("thisline",thisline)
        xdata = thisline.get_xdata()
        ydata = thisline.get_ydata()
        ind = event.ind
        points = tuple(zip(xdata[ind], ydata[ind]))                #If more than one point needs to be selected, this can be used
        a=xdata[ind[0]]
        b=ydata[ind[0]]   
        expected = ((a*dt)+43)*250                                         #ind[] contain more than one point coordinate indices when the picked dataset is large. Hence, we select the first one
        print('onpick point:', a,b)
        axs.plot(a,b, marker='x', color='red')
        axs.vlines(a-gate,b-1,b+1,linestyles = 'dashed',color = 'k')
        axs.vlines(a+gate,b-1,b+1,linestyles = 'dashed',color = 'm')
        axs.vlines(expected,b-1,b+1,linestyles = 'dashed',color = 'g')
        figg.canvas.draw()
        figg.canvas.flush_events()
        Average.append(int(a))
        time1.append(int(b))
        onpick.counter+=1
        print("counter ",onpick.counter)
        if onpick.counter==onpick.limit:
            plt.disconnect(cid)
            print("onpick event disconnected")                                           

    onpick.counter=0
    onpick.limit=limit

    cid=figg.canvas.mpl_connect('pick_event', onpick)
##    plt.grid()
    plt.legend()
##    plt.close(fig)
    plt.show()
    plt.close(figg)

    for ik in range(len(Average)):
        indice.append((np.argmax(y[Average[ik]-gate:Average[ik]+gate]))+Average[ik]-gate)

    return(indice)
