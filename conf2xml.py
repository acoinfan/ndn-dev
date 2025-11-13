from xml.dom import minidom
from confReader import configReader
import os

VERSION = "4.1"
ROUTING_MODE = "Floyd"
HOST_SPEED = "1Gf"

# 注: 目前只适用于每个最基础的node只有一个switch(寻路要求必须指出第一步才能自动使用dijkstra计算后续拓扑)
def main(conf_path: str):
    # Parsing conf file
    nodes, switches, links = configReader(conf_path)
    
    doc = minidom.Document()
    
    # Setting DTD
    impl = minidom.getDOMImplementation()
    doctype = impl.createDocumentType("platform", None, "https://simgrid.org/simgrid.dtd")
    doc.appendChild(doctype)
    
    
    # Create Root Node: platform
    platform = doc.createElement("platform")
    platform.setAttribute("version", VERSION)
    doc.appendChild(platform)
    
    # Create Child Node: platform/zone
    zone = doc.createElement("zone")
    zone.setAttribute("id", "AS0")
    zone.setAttribute("routing", ROUTING_MODE)
    platform.appendChild(zone)

    # Create Child Node: platform/zone/host
    zone.appendChild(doc.createComment("Node Definition"))
    for node in nodes:
        host = doc.createElement("host")
        host.setAttribute("id", node)
        host.setAttribute("speed", HOST_SPEED)
        zone.appendChild(host)
    
    # Create Child Node: platform/zone/router
    zone.appendChild(doc.createComment("Router Definition"))
    for switch in switches:
        router = doc.createElement("router")
        router.setAttribute("id", switch)
        zone.appendChild(router)

    # Create Child Node: platform/zone/link
    zone.appendChild(doc.createComment("Link Definition"))
    for link in links:
        docLink = doc.createElement("link")
        docLink.setAttribute("id", f"{link["src"]}_{link["dst"]}") # link format: client0_s0
        docLink.setAttribute("bandwidth", f"{link["bw"]}Mbps")
        docLink.setAttribute("latency", f"{link["delay"]}us")
        zone.appendChild(docLink)
        
    # Create Child Node: platform/zone/route
    zone.appendChild(doc.createComment("Route Definition"))
    for idx, src_node in enumerate(nodes):
        status = False
        for link in links:
            # prefix "s" refers to switches in Mini-ndn
            if link["src"] == src_node and link["dst"].startswith("s"):
                status = True
                for dst_node in nodes[idx+1:]:
                    docRoute = doc.createElement("route")
                    docRoute.setAttribute("src", src_node)
                    docRoute.setAttribute("dst", dst_node)
                    zone.appendChild(docRoute)
                    
                    link_ctn = doc.createElement("link_ctn")
                    link_ctn.setAttribute("id", f"{link["src"]}_{link["dst"]}")
                    docRoute.appendChild(link_ctn)
                break
            elif link["dst"] == src_node and link["src"].startswith("s"):
                status = True
                for dst_node in nodes[idx+1:]:
                    docRoute = doc.createElement("route")
                    docRoute.setAttribute("src", src_node)
                    docRoute.setAttribute("dst", dst_node)
                    zone.appendChild(docRoute)
                    
                    link_ctn = doc.createElement("link_ctn")
                    link_ctn.setAttribute("id", f"{link["dst"]}_{link["src"]}")
                    docRoute.appendChild(link_ctn)
                break
        if not status:
            raise RuntimeError(f"Failed to create first route for node {src_node}")
        
    # Write Back
    xml_path = os.path.splitext(conf_path)[0] + ".xml"
    with open(xml_path, "wb") as f:
        xml_str = doc.toprettyxml(indent=" ", newl="\n", encoding="utf-8")
        f.write(xml_str)


        
if __name__ == "__main__":
    import sys
    if len(sys.argv) == 2:
        main(sys.argv[1])
    else:
        main(f"Usage: python {sys.argv[0]} <topology file for minindn>")