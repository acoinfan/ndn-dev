import os
def parseLink(link: str) -> dict:
    list = link.split(' ')
    dict = {attribute[0]: attribute[1] for attribute in [attribute.split("=") for attribute in list[1:]]}
    dict["src"], dict["dst"] = list[0].split(":")
    return dict
    
def configReader(conf_path: str):
    if not os.path.exists(conf_path):
        raise RuntimeError(f"Invalid configDir: {conf_path}")
    
    with open(conf_path, 'r') as file:
        nodes, routers, links = [], [], []
        content = [line.strip() for line in file.readlines()] 
        nodeIdx, linkIdx = 0, 0
        try:
            nodeIdx = content.index("[nodes]")
        except ValueError:
            raise RuntimeError("Section Not Found: nodes") 
        
        try:
            linkIdx = content.index("[links]")
        except ValueError:
            raise RuntimeError("Section Not Found: links")
        
        for line in content[nodeIdx+1:]:
            if line.startswith("["):
                break
            elif line.startswith("client"):
                idx = line.find(":")
                nodes.append(line[0:idx])
            elif line.startswith("s"):
                idx = line.find(":")
                routers.append(line[0:idx])
                
        for line in content[linkIdx+1:]:
            if line.startswith("["):
                break
            elif line.startswith("s") or line.startswith("client"):
                link = parseLink(line)
                links.append(link)
        return nodes, routers, links
        
        
if __name__ == "__main__":
    import sys
    if len(sys.argv) == 2:
        configReader(sys.argv[1])
    else:
        print(f"Usage: python {sys.argv[0]} <configDir>")